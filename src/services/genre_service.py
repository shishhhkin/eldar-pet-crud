import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from src.db import is_unique_violation
from src.exceptions import GenreAlreadyExistsError, GenreNotFoundError
from src.mappers.genres import apply_genre_update, to_genre_model, to_genre_read
from src.models.genres import GenreModel
from src.repository import GenreRepo
from src.schemas.genres import GenreCreate, GenreRead, GenreUpdate
from src.services.base import BaseService

logger = logging.getLogger(__name__)


class GenreService(BaseService[GenreRepo]):
    async def _get_or_raise(self, genre_id: UUID, *options: ExecutableOption) -> GenreModel:
        genre = await self.repo.get(genre_id, *options)
        if genre is None:
            logger.info('genre not found: %s', genre_id)
            raise GenreNotFoundError(genre_id)
        return genre

    async def _save_or_raise(self, genre: GenreModel, *eager_load: str) -> None:
        try:
            await self.repo.save(genre, *eager_load)
        except IntegrityError as exc:
            if not is_unique_violation(exc):
                raise
            logger.info('genre already exists: %s', genre.name)
            raise GenreAlreadyExistsError from exc

    async def create(self, payload: GenreCreate) -> GenreRead:
        moods = await self.repo.upsert_moods([mood.name for mood in payload.moods])
        genre = to_genre_model(payload, moods)
        await self._save_or_raise(genre, 'moods')
        return to_genre_read(genre)

    async def get(self, genre_id: UUID) -> GenreRead:
        genre = await self._get_or_raise(genre_id, selectinload(GenreModel.moods))
        return to_genre_read(genre)

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreRead:
        genre = await self._get_or_raise(genre_id, selectinload(GenreModel.moods))
        apply_genre_update(genre, payload)
        if payload.moods is not None:
            genre.moods = list(await self.repo.upsert_moods([mood.name for mood in payload.moods]))
        await self._save_or_raise(genre, 'moods')
        return to_genre_read(genre)

    async def delete(self, genre_id: UUID) -> None:
        genre = await self._get_or_raise(genre_id)
        genre.is_deleted = True
        await self._save_or_raise(genre)
