from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql.base import ExecutableOption

from src.models.base import Base


class Repo[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def select(self) -> Select[tuple[ModelT]]:
        return select(self.model).options(
            with_loader_criteria(
                Base,
                lambda cls: cls.is_deleted.is_(False),
                include_aliases=True,
            )
        )

    async def scalars(self, stmt: Select[tuple[ModelT]]) -> Sequence[ModelT]:
        return (await self.session.execute(stmt)).scalars().all()

    async def list(self, *options: ExecutableOption, limit: int, offset: int) -> Sequence[ModelT]:
        stmt = self.select().options(*options).order_by(self.model.id).limit(limit).offset(offset)
        return (await self.session.execute(stmt)).scalars().all()

    async def get(self, obj_id: UUID, *options: ExecutableOption) -> ModelT | None:
        stmt = self.select().where(self.model.id == obj_id).options(*options)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def insert_ignoring_conflicts(
        self, rows: Sequence[dict[str, object]], *, index_elements: Sequence[str]
    ) -> None:
        if not rows:
            return
        stmt = (
            pg_insert(self.model)
            .values(list(rows))
            .on_conflict_do_nothing(
                index_elements=list(index_elements),
                index_where=text('is_deleted = false'),
            )
        )
        await self.session.execute(stmt)

    def add(self, instance: ModelT) -> None:
        self.session.add(instance)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, instance: ModelT, attribute_names: Sequence[str]) -> None:
        await self.session.refresh(instance, attribute_names=attribute_names)
