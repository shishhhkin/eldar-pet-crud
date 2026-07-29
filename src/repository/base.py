from uuid import UUID

from sqlalchemy import Select, select
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
