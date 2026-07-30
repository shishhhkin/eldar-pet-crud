import logging
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from src.exceptions import GenreAlreadyExistsError, GenreNotFoundError
from src.mappers.genres import apply_genre_update, to_genre_read
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

    async def create(self, payload: GenreCreate) -> GenreRead:
        moods = await self.repo.upsert_moods([mood.name for mood in payload.moods])
        await self.repo.advisory_lock('name', payload.name)
        genre = await self.repo.create_ignoring_conflict(payload.name)
        if genre is None:
            logger.info('genre already exists: %s', payload.name)
            raise GenreAlreadyExistsError
        genre.moods = list(moods)
        await self.repo.save(genre, 'moods')
        return to_genre_read(genre)

    async def get(self, genre_id: UUID) -> GenreRead:
        genre = await self._get_or_raise(genre_id, selectinload(GenreModel.moods))
        return to_genre_read(genre)

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreRead:
        genre = await self._get_or_raise(genre_id, selectinload(GenreModel.moods))
        if payload.name is not None:
            await self.repo.advisory_lock('name', payload.name)
            if await self.repo.exists(GenreModel.name == payload.name, GenreModel.id != genre_id):
                logger.info('genre already exists: %s', payload.name)
                raise GenreAlreadyExistsError
        apply_genre_update(genre, payload)
        if payload.moods is not None:
            genre.moods = list(await self.repo.upsert_moods([mood.name for mood in payload.moods]))
        await self.repo.save(genre, 'moods')
        return to_genre_read(genre)

    async def delete(self, genre_id: UUID) -> None:
        genre = await self._get_or_raise(genre_id)
        genre.is_deleted = True
        await self.repo.save(genre)
