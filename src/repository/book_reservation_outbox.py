from datetime import timedelta
from uuid import UUID

from sqlalchemy import Row, Text, cast, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.book_reservation_outbox import book_reservation_outbox
from src.schemas.book_reservations import BookReservationEvent

type ClaimedOutboxEntry = Row[tuple[UUID, UUID, str]]


class BookReservationOutboxRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: BookReservationEvent) -> None:
        stmt = insert(book_reservation_outbox).values(
            book_reservation_id=event.id, payload=event.model_dump(mode='json')
        )
        await self.session.execute(stmt)

    async def claim(self, lease: timedelta) -> ClaimedOutboxEntry | None:
        due = (
            select(book_reservation_outbox.c.book_reservation_id)
            .where(
                book_reservation_outbox.c.failed_at.is_(None),
                book_reservation_outbox.c.next_attempt_at <= func.now(),
            )
            .order_by(book_reservation_outbox.c.next_attempt_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(book_reservation_outbox)
            .where(book_reservation_outbox.c.book_reservation_id == due)
            .values(next_attempt_at=func.now() + lease, claim_token=func.gen_random_uuid())
            .returning(
                book_reservation_outbox.c.book_reservation_id,
                book_reservation_outbox.c.claim_token,
                cast(book_reservation_outbox.c.payload, Text).label('payload'),
            )
        )
        return (await self.session.execute(stmt)).one_or_none()

    async def complete(self, book_reservation_id: UUID, claim_token: UUID) -> bool:
        stmt = (
            delete(book_reservation_outbox)
            .where(
                book_reservation_outbox.c.book_reservation_id == book_reservation_id,
                book_reservation_outbox.c.claim_token == claim_token,
            )
            .returning(book_reservation_outbox.c.book_reservation_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def release(self, book_reservation_id: UUID, claim_token: UUID) -> None:
        stmt = (
            update(book_reservation_outbox)
            .where(
                book_reservation_outbox.c.book_reservation_id == book_reservation_id,
                book_reservation_outbox.c.claim_token == claim_token,
            )
            .values(next_attempt_at=func.now())
        )
        await self.session.execute(stmt)

    async def fail(self, book_reservation_id: UUID, claim_token: UUID) -> None:
        stmt = (
            update(book_reservation_outbox)
            .where(
                book_reservation_outbox.c.book_reservation_id == book_reservation_id,
                book_reservation_outbox.c.claim_token == claim_token,
            )
            .values(failed_at=func.now())
        )
        await self.session.execute(stmt)
