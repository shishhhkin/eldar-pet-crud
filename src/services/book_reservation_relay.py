import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, MessageSizeTooLargeError

from src.infra.db import UnitOfWork
from src.repository import BookReservationOutboxRepo
from src.repository.book_reservation_outbox import ClaimedOutboxEntry

logger = logging.getLogger(__name__)


class BookReservationRelay:
    def __init__(
        self,
        uow: UnitOfWork,
        outbox: BookReservationOutboxRepo,
        producer: AIOKafkaProducer,
        topic: str,
        pass_limit: int,
        interval_seconds: float,
        lease_seconds: float,
        send_timeout_seconds: float,
        heartbeat: Callable[[], None] = lambda: None,
    ) -> None:
        self.uow = uow
        self.outbox = outbox
        self.producer = producer
        self.topic = topic
        self.pass_limit = pass_limit
        self.interval_seconds = interval_seconds
        self.lease = timedelta(seconds=lease_seconds)
        self.send_timeout_seconds = send_timeout_seconds
        self.heartbeat = heartbeat
        self.stopping = asyncio.Event()

    def stop(self) -> None:
        self.stopping.set()

    async def process_pass(self) -> int:
        processed = 0
        while processed < self.pass_limit and not self.stopping.is_set():
            async with self.uow:
                claimed = await self.outbox.claim(self.lease)
            self.heartbeat()
            if claimed is None:
                break
            processed += 1
            if not await self._publish(claimed):
                break
        return processed

    async def run(self) -> None:
        while not self.stopping.is_set():
            try:
                await self.process_pass()
            except Exception:
                logger.exception('book reservation relay failed')
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stopping.wait(), self.interval_seconds)

    async def _publish(self, claimed: ClaimedOutboxEntry) -> bool:
        reservation_id = claimed.book_reservation_id
        claim_token = claimed.claim_token
        try:
            async with asyncio.timeout(self.send_timeout_seconds):
                await self.producer.send_and_wait(
                    self.topic,
                    key=str(reservation_id).encode(),
                    value=claimed.payload.encode(),
                )
        except MessageSizeTooLargeError as exc:
            logger.error('book reservation rejected by kafka: id=%s (%s)', reservation_id, exc)
            async with self.uow:
                await self.outbox.fail(reservation_id, claim_token)
            return True
        except (KafkaError, TimeoutError) as exc:
            logger.warning('book reservation publish deferred: id=%s (%r)', reservation_id, exc)
            async with self.uow:
                await self.outbox.release(reservation_id, claim_token)
            return False
        async with self.uow:
            if not await self.outbox.complete(reservation_id, claim_token):
                logger.warning('book reservation published after reclaim: id=%s', reservation_id)
        return True
