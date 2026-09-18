from collections.abc import Sequence
from typing import Final, cast
from uuid import UUID

from sqlalchemy import Row, delete, insert, select
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
        self, limit: int, ids: Sequence[UUID] | None = None
    ) -> Sequence[Row[tuple[UUID, str]]]:
        stmt = (
            select(cache_invalidations.c.id, cache_invalidations.c.key)
            .order_by(cache_invalidations.c.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if ids is not None:
            stmt = stmt.where(cache_invalidations.c.id.in_(ids))
        return (await self.session.execute(stmt)).all()

    async def delete(self, ids: Sequence[UUID]) -> None:
        stmt = delete(cache_invalidations).where(cache_invalidations.c.id.in_(ids))
        await self.session.execute(stmt)
