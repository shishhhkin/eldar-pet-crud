from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pending_memberships import pending_memberships


class PendingMembershipRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, delay: timedelta) -> None:
        stmt = insert(pending_memberships).values(
            user_id=user_id, next_attempt_at=func.now() + delay
        )
        await self.session.execute(stmt)

    async def claim(self, lease: timedelta) -> UUID | None:
        due = (
            select(pending_memberships.c.user_id)
            .where(
                pending_memberships.c.failed_at.is_(None),
                pending_memberships.c.next_attempt_at <= func.now(),
            )
            .order_by(pending_memberships.c.next_attempt_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(pending_memberships)
            .where(pending_memberships.c.user_id == due)
            .values(next_attempt_at=func.now() + lease)
            .returning(pending_memberships.c.user_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def fail(self, user_id: UUID) -> None:
        stmt = (
            update(pending_memberships)
            .where(pending_memberships.c.user_id == user_id)
            .values(failed_at=func.now())
        )
        await self.session.execute(stmt)

    async def release(self, user_id: UUID) -> None:
        stmt = (
            update(pending_memberships)
            .where(pending_memberships.c.user_id == user_id)
            .values(next_attempt_at=func.now())
        )
        await self.session.execute(stmt)

    async def complete(self, user_id: UUID) -> bool:
        stmt = (
            delete(pending_memberships)
            .where(pending_memberships.c.user_id == user_id)
            .returning(pending_memberships.c.user_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def cancel(self, user_id: UUID) -> None:
        stmt = delete(pending_memberships).where(pending_memberships.c.user_id == user_id)
        await self.session.execute(stmt)
