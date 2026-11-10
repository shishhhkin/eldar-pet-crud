import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, Self
from uuid import UUID

import pytest
from aiokafka import AIOKafkaProducer
from aiokafka.structs import ConsumerRecord
from httpx import AsyncClient
from sqlalchemy import Row, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.db import UnitOfWork, tx_session
from src.models import book_reservation_outbox
from src.repository import BookReservationOutboxRepo
from src.repository.book_reservation_outbox import ClaimedOutboxEntry
from src.schemas.book_reservations import BookReservationRead
from src.services.book_reservation_relay import BookReservationRelay
from tests.conftest import (
    BOOK_RESERVATION_RELAY_INTERVAL_SECONDS,
    BOOK_RESERVATION_RELAY_LEASE_SECONDS,
    BOOK_RESERVATION_RELAY_PASS_LIMIT,
    KAFKA_SEND_TIMEOUT_SECONDS,
    KafkaOutage,
    Reserve,
    make_relay,
    read_messages,
    reservation_event,
    topic_size,
)

RELAY_LOGGER = 'src.services.book_reservation_relay'
WAIT_TIMEOUT_SECONDS = 10.0
POLL_SECONDS = 0.01
LEASE = timedelta(seconds=BOOK_RESERVATION_RELAY_LEASE_SECONDS)
CLOCK_TOLERANCE = timedelta(seconds=1)
HELD_SEND_TIMEOUT_SECONDS = 10.0
OVERSIZED_TITLE = 'x' * 1_100_000

type Settle = Callable[[BookReservationOutboxRepo, UUID, UUID], Awaitable[object]]


async def _outbox(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[UUID, tuple[datetime | None, timedelta]]:
    async with session_factory() as session:
        stmt = select(
            book_reservation_outbox.c.book_reservation_id,
            book_reservation_outbox.c.failed_at,
            book_reservation_outbox.c.next_attempt_at - func.now(),
        ).order_by(book_reservation_outbox.c.created_at)
        return {
            reservation_id: (failed_at, wait)
            for reservation_id, failed_at, wait in await session.execute(stmt)
        }


async def _row(
    session_factory: async_sessionmaker[AsyncSession], reservation_id: UUID
) -> Row[tuple[datetime, UUID, datetime | None]]:
    async with session_factory() as session:
        stmt = select(
            book_reservation_outbox.c.next_attempt_at,
            book_reservation_outbox.c.claim_token,
            book_reservation_outbox.c.failed_at,
        ).where(book_reservation_outbox.c.book_reservation_id == reservation_id)
        return (await session.execute(stmt)).one()


async def _claim(session_factory: async_sessionmaker[AsyncSession]) -> ClaimedOutboxEntry | None:
    async with tx_session(session_factory) as session:
        return await BookReservationOutboxRepo(session).claim(LEASE)


async def _expire_lease(
    session_factory: async_sessionmaker[AsyncSession], reservation_id: UUID
) -> None:
    async with tx_session(session_factory) as session:
        await session.execute(
            update(book_reservation_outbox)
            .where(book_reservation_outbox.c.book_reservation_id == reservation_id)
            .values(next_attempt_at=func.now() - CLOCK_TOLERANCE)
        )


async def _inflate_payload(
    session_factory: async_sessionmaker[AsyncSession], reservation_id: UUID
) -> None:
    async with tx_session(session_factory) as session:
        await session.execute(
            update(book_reservation_outbox)
            .where(book_reservation_outbox.c.book_reservation_id == reservation_id)
            .values(payload={'title': OVERSIZED_TITLE})
        )


async def _db_now(session_factory: async_sessionmaker[AsyncSession]) -> datetime:
    async with session_factory() as session:
        return (await session.execute(select(func.now()))).scalar_one()


async def _wait_until_claimed(
    session_factory: async_sessionmaker[AsyncSession], reservation_id: UUID
) -> None:
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        while (await _outbox(session_factory))[reservation_id][1] <= timedelta(0):
            await asyncio.sleep(POLL_SECONDS)


async def _drain(
    relay: BookReservationRelay, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        while await _outbox(session_factory):
            await relay.process_pass()
            await asyncio.sleep(BOOK_RESERVATION_RELAY_INTERVAL_SECONDS)


def _decoded(records: list[ConsumerRecord]) -> list[tuple[str, Any]]:
    return [(record.key.decode(), json.loads(record.value)) for record in records]


def _event(reservation: BookReservationRead) -> tuple[str, Any]:
    return str(reservation.id), reservation_event(reservation.model_dump(mode='json'))


async def test_pass_publishes_reservations_and_removes_them_from_outbox(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    kafka_topic: str,
) -> None:
    reservations = [await reserve('Мастер и Маргарита'), await reserve('Белая гвардия')]

    assert await relay.process_pass() == 2

    records = await read_messages(kafka_bootstrap, kafka_topic, 2)
    assert _decoded(records) == [_event(reservation) for reservation in reservations]
    assert await _outbox(session_factory) == {}


async def test_reservation_created_via_api_is_published_with_response_fields(
    client: AsyncClient,
    relay: BookReservationRelay,
    kafka_bootstrap: str,
    kafka_topic: str,
) -> None:
    response = await client.post(
        '/book-reservations', json={'title': 'Мастер и Маргарита', 'author': 'Михаил Булгаков'}
    )
    assert response.status_code == 201

    assert await relay.process_pass() == 1

    records = await read_messages(kafka_bootstrap, kafka_topic, 1)
    assert _decoded(records) == [(response.json()['id'], reservation_event(response.json()))]


async def test_pass_is_limited_by_pass_limit(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    kafka_producer: AIOKafkaProducer,
    kafka_topic: str,
    reserve: Reserve,
) -> None:
    await reserve('Мастер и Маргарита')
    await reserve('Белая гвардия')

    relay = make_relay(db_session, kafka_producer, kafka_topic, pass_limit=1)
    assert await relay.process_pass() == 1

    assert len(await _outbox(session_factory)) == 1


async def test_pass_skips_reservation_leased_by_another_relay(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    kafka_topic: str,
) -> None:
    await reserve()
    assert await _claim(session_factory) is not None

    assert await relay.process_pass() == 0
    assert await topic_size(kafka_bootstrap, kafka_topic) == 0


async def test_pass_takes_reservation_whose_lease_expired(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    kafka_topic: str,
) -> None:
    reservation = await reserve()
    assert await _claim(session_factory) is not None
    await _expire_lease(session_factory, reservation.id)

    assert await relay.process_pass() == 1

    assert await _outbox(session_factory) == {}
    assert await topic_size(kafka_bootstrap, kafka_topic) == 1


async def test_claim_returns_payload_and_new_token(
    reserve: Reserve, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    reservation = await reserve()
    added_token = (await _row(session_factory, reservation.id)).claim_token

    claimed = await _claim(session_factory)

    assert claimed is not None
    assert claimed.book_reservation_id == reservation.id
    assert json.loads(claimed.payload) == reservation_event(reservation.model_dump(mode='json'))
    assert reservation.title in claimed.payload
    assert claimed.claim_token != added_token
    assert (await _row(session_factory, reservation.id)).claim_token == claimed.claim_token


@pytest.mark.parametrize(
    'settle',
    [
        BookReservationOutboxRepo.complete,
        BookReservationOutboxRepo.release,
        BookReservationOutboxRepo.fail,
    ],
    ids=['complete', 'release', 'fail'],
)
async def test_stale_token_does_not_settle_reclaimed_reservation(
    reserve: Reserve, session_factory: async_sessionmaker[AsyncSession], settle: Settle
) -> None:
    reservation = await reserve()
    stale = await _claim(session_factory)
    assert stale is not None
    await _expire_lease(session_factory, reservation.id)
    assert await _claim(session_factory) is not None
    reclaimed = await _row(session_factory, reservation.id)

    async with tx_session(session_factory) as session:
        await settle(BookReservationOutboxRepo(session), reservation.id, stale.claim_token)

    assert await _row(session_factory, reservation.id) == reclaimed


async def test_claim_skips_failed_reservation(
    reserve: Reserve, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    reservation = await reserve()
    claimed = await _claim(session_factory)
    assert claimed is not None
    async with tx_session(session_factory) as session:
        await BookReservationOutboxRepo(session).fail(reservation.id, claimed.claim_token)
    await _expire_lease(session_factory, reservation.id)

    assert await _claim(session_factory) is None


async def test_concurrent_claims_take_different_reservations(
    reserve: Reserve, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    reservation_ids = {(await reserve('Мастер и Маргарита')).id, (await reserve('Бег')).id}

    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        async with tx_session(session_factory) as first:
            held = await BookReservationOutboxRepo(first).claim(LEASE)
            async with tx_session(session_factory) as second:
                other = await BookReservationOutboxRepo(second).claim(LEASE)

    assert held is not None
    assert other is not None
    assert {held.book_reservation_id, other.book_reservation_id} == reservation_ids


async def test_pass_stops_and_releases_reservation_while_kafka_is_down(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_outage: KafkaOutage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    first, second = await reserve('Мастер и Маргарита'), await reserve('Белая гвардия')

    with caplog.at_level(logging.WARNING, logger=RELAY_LOGGER), kafka_outage():
        assert await relay.process_pass() == 1

    outbox = await _outbox(session_factory)
    assert list(outbox) == [first.id, second.id]
    assert all(failed_at is None for failed_at, _ in outbox.values())
    assert all(wait <= timedelta(0) for _, wait in outbox.values())
    assert any(str(first.id) in record.getMessage() for record in caplog.records)


async def test_reservation_kept_during_outage_is_published_when_kafka_is_back(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_outage: KafkaOutage,
    kafka_bootstrap: str,
    kafka_topic: str,
) -> None:
    reservation = await reserve()
    with kafka_outage():
        assert await relay.process_pass() == 1

    await _drain(relay, session_factory)

    records = await read_messages(kafka_bootstrap, kafka_topic, 1)
    assert {key for key, _ in _decoded(records)} == {str(reservation.id)}


async def test_oversized_reservation_fails_and_pass_continues(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    kafka_topic: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    rejected, published = await reserve('Мастер и Маргарита'), await reserve('Белая гвардия')
    await _inflate_payload(session_factory, rejected.id)
    before = await _db_now(session_factory)

    with caplog.at_level(logging.ERROR, logger=RELAY_LOGGER):
        assert await relay.process_pass() == 2

    outbox = await _outbox(session_factory)
    assert list(outbox) == [rejected.id]
    failed_at, _ = outbox[rejected.id]
    assert failed_at is not None
    assert before < failed_at < await _db_now(session_factory)
    assert _decoded(await read_messages(kafka_bootstrap, kafka_topic, 1)) == [_event(published)]
    assert await topic_size(kafka_bootstrap, kafka_topic) == 1
    assert any(str(rejected.id) in record.getMessage() for record in caplog.records)


async def test_failed_reservation_is_not_retried(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    reservation = await reserve()
    await _inflate_payload(session_factory, reservation.id)
    assert await relay.process_pass() == 1

    await _expire_lease(session_factory, reservation.id)

    assert await relay.process_pass() == 0
    assert (await _row(session_factory, reservation.id)).failed_at is not None


async def test_relay_with_expired_lease_does_not_complete_reclaimed_reservation(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    kafka_producer: AIOKafkaProducer,
    kafka_topic: str,
    kafka_bootstrap: str,
    kafka_outage: KafkaOutage,
    reserve: Reserve,
    caplog: pytest.LogCaptureFixture,
) -> None:
    reservation = await reserve()
    stale_relay = make_relay(
        db_session,
        kafka_producer,
        kafka_topic,
        send_timeout_seconds=HELD_SEND_TIMEOUT_SECONDS,
    )

    with caplog.at_level(logging.WARNING, logger=RELAY_LOGGER):
        with kafka_outage():
            stale_pass = asyncio.create_task(stale_relay.process_pass())
            await _wait_until_claimed(session_factory, reservation.id)
            await _expire_lease(session_factory, reservation.id)
            assert await _claim(session_factory) is not None
            reclaimed = await _row(session_factory, reservation.id)
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            assert await stale_pass == 1

    assert await _row(session_factory, reservation.id) == reclaimed
    assert await topic_size(kafka_bootstrap, kafka_topic) == 1
    assert any(
        'after reclaim' in record.getMessage() and str(reservation.id) in record.getMessage()
        for record in caplog.records
    )


async def test_run_loop_publishes_reservations_added_later(
    relay: BookReservationRelay,
    reserve: Reserve,
    session_factory: async_sessionmaker[AsyncSession],
    kafka_bootstrap: str,
    kafka_topic: str,
) -> None:
    worker = asyncio.create_task(relay.run())
    try:
        reservation = await reserve()
        records = await read_messages(kafka_bootstrap, kafka_topic, 1)
    finally:
        relay.stop()
        async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
            await worker

    assert _decoded(records) == [_event(reservation)]
    assert await _outbox(session_factory) == {}


async def test_stop_finishes_send_in_flight_and_leaves_rest_of_pass(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    kafka_producer: AIOKafkaProducer,
    kafka_topic: str,
    kafka_bootstrap: str,
    kafka_outage: KafkaOutage,
    reserve: Reserve,
) -> None:
    first, second = await reserve('Мастер и Маргарита'), await reserve('Белая гвардия')
    relay = make_relay(
        db_session,
        kafka_producer,
        kafka_topic,
        send_timeout_seconds=HELD_SEND_TIMEOUT_SECONDS,
    )

    with kafka_outage():
        worker = asyncio.create_task(relay.run())
        await _wait_until_claimed(session_factory, first.id)
        relay.stop()
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        await worker

    assert list(await _outbox(session_factory)) == [second.id]
    assert _decoded(await read_messages(kafka_bootstrap, kafka_topic, 1)) == [_event(first)]
    assert await topic_size(kafka_bootstrap, kafka_topic) == 1


async def test_run_logs_failed_iteration_and_keeps_publishing(
    db_session: AsyncSession,
    kafka_producer: AIOKafkaProducer,
    kafka_topic: str,
    kafka_bootstrap: str,
    reserve: Reserve,
    caplog: pytest.LogCaptureFixture,
) -> None:
    reservation = await reserve()

    class FailingOnceUnitOfWork(UnitOfWork):
        failed = False

        async def __aenter__(self) -> Self:
            if not self.failed:
                self.failed = True
                raise RuntimeError('unexpected failure')
            return await super().__aenter__()

    relay = BookReservationRelay(
        FailingOnceUnitOfWork(db_session),
        BookReservationOutboxRepo(db_session),
        kafka_producer,
        kafka_topic,
        BOOK_RESERVATION_RELAY_PASS_LIMIT,
        BOOK_RESERVATION_RELAY_INTERVAL_SECONDS,
        BOOK_RESERVATION_RELAY_LEASE_SECONDS,
        KAFKA_SEND_TIMEOUT_SECONDS,
    )

    with caplog.at_level(logging.ERROR, logger=RELAY_LOGGER):
        worker = asyncio.create_task(relay.run())
        try:
            records = await read_messages(kafka_bootstrap, kafka_topic, 1)
        finally:
            relay.stop()
            async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
                await worker

    assert _decoded(records) == [_event(reservation)]
    relay_records = [record for record in caplog.records if record.name == RELAY_LOGGER]
    assert [record.levelno for record in relay_records] == [logging.ERROR]
