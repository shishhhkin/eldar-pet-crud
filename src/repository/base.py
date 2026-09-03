from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ColumnExpressionArgument, Select, TextClause, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql.base import ExecutableOption

from src.models.base import Base


def active_only() -> ExecutableOption:
    return with_loader_criteria(
        Base,
        lambda cls: cls.is_deleted.is_(False),
        include_aliases=True,
    )


class Repo[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def select(self) -> Select[tuple[ModelT]]:
        return select(self.model).options(active_only())

    async def get(self, obj_id: UUID, *options: ExecutableOption) -> ModelT | None:
        stmt = self.select().where(self.model.id == obj_id).options(*options)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save(self, obj: ModelT, *eager_load: str) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        if eager_load:
            await self.session.refresh(obj, attribute_names=list(eager_load))
        return obj

    async def advisory_lock(self, column: str, value: str) -> None:
        namespace = f'{self.model.__tablename__}.{column}'
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(namespace), func.hashtext(value)))
        )

    async def exists(self, *predicates: ColumnExpressionArgument[bool]) -> bool:
        stmt = self.select().where(*predicates).with_only_columns(self.model.id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def insert_ignoring_conflict(
        self,
        *,
        index_elements: Sequence[str] | None = None,
        index_where: TextClause | None = None,
        **values: object,
    ) -> ModelT | None:
        stmt = (
            pg_insert(self.model)
            .values(**values)
            .on_conflict_do_nothing(index_elements=index_elements, index_where=index_where)
            .returning(self.model)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
