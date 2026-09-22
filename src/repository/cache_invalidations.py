from collections.abc import Sequence
from datetime import timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import Row, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cache_invalidations import cache_invalidations

PENDING_INVALIDATIONS: Final = 'pending_cache_invalidations'


def pop_pending_invalidations(session: AsyncSession) -> list[UUID]:
    return cast('list[UUID]', session.info.pop(PENDING_INVALIDATIONS, []))


class CacheInvalidationRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, key: str) -> None:
        stmt = insert(cache_invalidations).values(key=key).returning(cache_invalidations.c.id)
        invalidation_id = (await self.session.execute(stmt)).scalar_one()
        self.session.info.setdefault(PENDING_INVALIDATIONS, []).append(invalidation_id)

    async def claim(
        self, limit: int, lease: timedelta, ids: Sequence[UUID] | None = None
    ) -> Sequence[Row[tuple[UUID, str]]]:
        stmt = (
            select(cache_invalidations.c.id, cache_invalidations.c.key)
            .where(
                or_(
                    cache_invalidations.c.claimed_until.is_(None),
                    cache_invalidations.c.claimed_until < func.now(),
                )
            )
            .order_by(cache_invalidations.c.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if ids is not None:
            stmt = stmt.where(cache_invalidations.c.id.in_(ids))
        claimed = (await self.session.execute(stmt)).all()
        if claimed:
            lease_stmt = (
                update(cache_invalidations)
                .where(cache_invalidations.c.id.in_([row.id for row in claimed]))
                .values(claimed_until=func.now() + lease)
            )
            await self.session.execute(lease_stmt)
        return claimed

    async def release(self, ids: Sequence[UUID]) -> None:
        stmt = (
            update(cache_invalidations)
            .where(cache_invalidations.c.id.in_(ids))
            .values(claimed_until=None)
        )
        await self.session.execute(stmt)

    async def delete(self, ids: Sequence[UUID]) -> None:
        stmt = delete(cache_invalidations).where(cache_invalidations.c.id.in_(ids))
        await self.session.execute(stmt)
