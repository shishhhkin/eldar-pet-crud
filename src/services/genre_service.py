import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ConstraintViolationError, ObjectNotFoundError
from src.models.genres import GenreModel
from src.schemas.genres import GenreCreate, GenreUpdate

logger = logging.getLogger(__name__)


class GenreService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_with_books(self, genre_id: UUID) -> GenreModel:
        stmt = (
            select(GenreModel)
            .where(GenreModel.id == genre_id)
            .options(selectinload(GenreModel.books))
        )
        genre = (await self.session.execute(stmt)).scalar_one_or_none()
        if genre is None:
            raise ObjectNotFoundError(GenreModel, genre_id)
        return genre

    async def create(self, payload: GenreCreate) -> GenreModel:
        genre = GenreModel(**payload.model_dump())
        self.session.add(genre)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error creating genre: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(f'failed to create genre: {str(e.orig)}') from e
        await self.session.refresh(genre, attribute_names=['books'])
        return genre

    async def get(self, genre_id: UUID) -> GenreModel:
        return await self._get_with_books(genre_id)

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreModel:
        genre = await self._get_with_books(genre_id)
        for field, value in payload.model_dump().items():
            setattr(genre, field, value)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error updating genre {genre_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to update genre {genre_id}: {str(e.orig)}'
            ) from e
        return genre

    async def delete(self, genre_id: UUID) -> None:
        genre = await self._get_with_books(genre_id)
        await self.session.delete(genre)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error deleting genre {genre_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to delete genre {genre_id}: {str(e.orig)}'
            ) from e
