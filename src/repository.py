from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql.base import ExecutableOption

from src.exceptions import ObjectNotFoundError
from src.models.base import Base


class Repo[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def select(self, *, include_deleted: bool = False) -> Select[tuple[ModelT]]:
        stmt = select(self.model)
        if not include_deleted:
            stmt = stmt.options(
                with_loader_criteria(
                    Base,
                    lambda cls: cls.is_deleted.is_(False),
                    include_aliases=True,
                )
            )
        return stmt

    async def scalars(self, stmt: Select[tuple[ModelT]]) -> Sequence[ModelT]:
        return (await self.session.execute(stmt)).scalars().all()

    async def get(
        self, obj_id: UUID, *options: ExecutableOption, include_deleted: bool = False
    ) -> ModelT:
        stmt = (
            self.select(include_deleted=include_deleted)
            .where(self.model.id == obj_id)
            .options(*options)
        )
        obj = (await self.session.execute(stmt)).scalar_one_or_none()
        if obj is None:
            raise ObjectNotFoundError(self.model, obj_id)
        return obj

    def add(self, instance: ModelT) -> None:
        self.session.add(instance)

    def add_all(self, instances: Sequence[ModelT]) -> None:
        self.session.add_all(instances)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, instance: ModelT, attribute_names: Sequence[str]) -> None:
        await self.session.refresh(instance, attribute_names=attribute_names)
