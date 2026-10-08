from datetime import timedelta
from uuid import UUID

from sqlalchemy import Row, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.membership_requests import membership_requests


class MembershipRequestRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, delay: timedelta) -> None:
        stmt = insert(membership_requests).values(
            user_id=user_id, next_attempt_at=func.now() + delay
        )
        await self.session.execute(stmt)

    async def claim(self, lease: timedelta) -> Row[tuple[UUID, int]] | None:
        due = (
            select(membership_requests.c.user_id)
            .where(membership_requests.c.next_attempt_at <= func.now())
            .order_by(membership_requests.c.next_attempt_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(membership_requests)
            .where(membership_requests.c.user_id == due)
            .values(next_attempt_at=func.now() + lease)
            .returning(membership_requests.c.user_id, membership_requests.c.attempts)
        )
        return (await self.session.execute(stmt)).one_or_none()

    async def reschedule(self, user_id: UUID, attempts: int, delay: timedelta) -> None:
        stmt = (
            update(membership_requests)
            .where(membership_requests.c.user_id == user_id)
            .values(attempts=attempts, next_attempt_at=func.now() + delay)
        )
        await self.session.execute(stmt)

    async def release(self, user_id: UUID) -> None:
        stmt = (
            update(membership_requests)
            .where(membership_requests.c.user_id == user_id)
            .values(next_attempt_at=func.now())
        )
        await self.session.execute(stmt)

    async def complete(self, user_id: UUID) -> bool:
        stmt = (
            delete(membership_requests)
            .where(membership_requests.c.user_id == user_id)
            .returning(membership_requests.c.user_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def cancel(self, user_id: UUID) -> None:
        stmt = delete(membership_requests).where(membership_requests.c.user_id == user_id)
        await self.session.execute(stmt)
