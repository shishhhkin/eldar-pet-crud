from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.db import tx_session
from src.models import BookReservationModel, book_reservation_outbox
from tests.conftest import reservation_event

PAYLOAD = {'title': 'Мастер и Маргарита', 'author': 'Михаил Булгаков'}


async def _reservations(session_factory: async_sessionmaker[AsyncSession]) -> list[UUID]:
    async with session_factory() as session:
        return list((await session.execute(select(BookReservationModel.id))).scalars())


async def _outbox(session_factory: async_sessionmaker[AsyncSession]) -> dict[UUID, Any]:
    async with session_factory() as session:
        stmt = select(
            book_reservation_outbox.c.book_reservation_id, book_reservation_outbox.c.payload
        )
        return {reservation_id: payload for reservation_id, payload in await session.execute(stmt)}


async def test_create_book_reservation_stores_event_with_response_fields(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post('/book-reservations', json=PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body['title'] == PAYLOAD['title']
    assert body['author'] == PAYLOAD['author']
    assert await _reservations(session_factory) == [UUID(body['id'])]
    assert await _outbox(session_factory) == {UUID(body['id']): reservation_event(body)}


async def test_create_book_reservation_normalizes_text(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post(
        '/book-reservations',
        json={'title': '  Мастер   и​ Маргарита ', 'author': '\tМихаил  Булгаков\n'},
    )

    assert response.status_code == 201
    body = response.json()
    assert (body['title'], body['author']) == ('Мастер и Маргарита', 'Михаил Булгаков')
    event = (await _outbox(session_factory))[UUID(body['id'])]
    assert (event['title'], event['author']) == ('Мастер и Маргарита', 'Михаил Булгаков')


@pytest.mark.parametrize(
    'payload',
    [
        {'title': '', 'author': 'Михаил Булгаков'},
        {'title': '   ', 'author': 'Михаил Булгаков'},
        {'title': 'М' * 256, 'author': 'Михаил Булгаков'},
        {'title': None, 'author': 'Михаил Булгаков'},
        {'title': 'Мастер и Маргарита', 'author': 'М' * 129},
        {'title': 'Мастер и Маргарита'},
        {},
    ],
    ids=[
        'empty_title',
        'blank_title',
        'long_title',
        'null_title',
        'long_author',
        'no_author',
        'empty',
    ],
)
async def test_invalid_book_reservation_is_rejected_without_writes(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], payload: dict
) -> None:
    response = await client.post('/book-reservations', json=payload)

    assert response.status_code == 422
    assert await _reservations(session_factory) == []
    assert await _outbox(session_factory) == {}


async def test_reservation_is_not_stored_when_outbox_write_fails(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with tx_session(session_factory) as session:
        await session.execute(text('DROP TABLE book_reservation_outbox'))

    with pytest.raises(ProgrammingError):
        await client.post('/book-reservations', json=PAYLOAD)

    assert await _reservations(session_factory) == []
