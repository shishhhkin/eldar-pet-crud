import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ConstraintViolationError, ObjectNotFoundError
from src.models.authors import AuthorModel
from src.schemas.authors import AuthorCreate, AuthorUpdate

logger = logging.getLogger(__name__)


class AuthorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_with_books(self, author_id: UUID) -> AuthorModel:
        stmt = (
            select(AuthorModel)
            .where(AuthorModel.id == author_id)
            .options(selectinload(AuthorModel.books))
        )
        author = (await self.session.execute(stmt)).scalar_one_or_none()
        if author is None:
            raise ObjectNotFoundError(AuthorModel, author_id)
        return author

    async def create(self, payload: AuthorCreate) -> AuthorModel:
        author = AuthorModel(**payload.model_dump())
        self.session.add(author)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error creating author: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(f'failed to create author: {str(e.orig)}') from e
        await self.session.refresh(author, attribute_names=['books'])
        return author

    async def get(self, author_id: UUID) -> AuthorModel:
        return await self._get_with_books(author_id)

    async def update(self, author_id: UUID, payload: AuthorUpdate) -> AuthorModel:
        author = await self._get_with_books(author_id)
        for field, value in payload.model_dump().items():
            setattr(author, field, value)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error updating author {author_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to update author {author_id}: {str(e.orig)}'
            ) from e
        return author

    async def delete(self, author_id: UUID) -> None:
        author = await self._get_with_books(author_id)
        await self.session.delete(author)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error deleting author {author_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to delete author {author_id}: {str(e.orig)}'
            ) from e
