import logging
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.sql.base import ExecutableOption

from src.exceptions import AlreadyExistsError
from src.models.base import Base

logger = logging.getLogger(__name__)

UNIQUE_VIOLATION = '23505'


def active_only() -> ExecutableOption:
    return with_loader_criteria(
        Base,
        lambda cls: cls.is_deleted.is_(False),
        include_aliases=True,
    )


def _is_unique_violation(exc: IntegrityError) -> bool:
    return getattr(exc.orig, 'sqlstate', None) == UNIQUE_VIOLATION


class Repo[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def select(self) -> Select[tuple[ModelT]]:
        return select(self.model).options(active_only())

    async def get(self, obj_id: UUID, *options: ExecutableOption) -> ModelT | None:
        stmt = self.select().where(self.model.id == obj_id).options(*options)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def save(self, obj: ModelT, *refresh: str) -> ModelT:
        self.session.add(obj)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            if _is_unique_violation(exc):
                name = self.model.__name__.removesuffix('Model')
                logger.info('already exists: %s', name)
                raise AlreadyExistsError(name) from exc
            raise
        if refresh:
            await self.session.refresh(obj, attribute_names=list(refresh))
        return obj
