import logging
from uuid import UUID

from src.exceptions import AlreadyExistsError
from src.mappers.genres import apply_genre_update
from src.models.genres import GenreModel
from src.repository import GenreRepo
from src.schemas.genres import GenreCreate, GenreRead, GenreUpdate
from src.services.base import BaseService

logger = logging.getLogger(__name__)


class GenreService(BaseService[GenreRepo, GenreModel, GenreRead]):
    entity_name = 'Genre'
    cache_namespace = 'genre'
    read_model = GenreRead

    async def create(self, payload: GenreCreate) -> GenreRead:
        moods = await self.repo.upsert_moods([mood.name for mood in payload.moods])
        await self.repo.advisory_lock('name', payload.name)
        genre = await self.repo.create_ignoring_conflict(payload.name)
        if genre is None:
            logger.info('genre already exists: %s', payload.name)
            raise AlreadyExistsError('Genre with this name already exists')
        genre.moods = list(moods)
        await self.repo.save(genre, 'moods')
        return self.read_model.model_validate(genre)

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreRead:
        genre = await self._get_or_raise(genre_id)
        if payload.name is not None:
            await self.repo.advisory_lock('name', payload.name)
            if await self.repo.exists(GenreModel.name == payload.name, GenreModel.id != genre_id):
                logger.info('genre already exists: %s', payload.name)
                raise AlreadyExistsError('Genre with this name already exists')
        apply_genre_update(genre, payload)
        if payload.moods is not None:
            genre.moods = list(await self.repo.upsert_moods([mood.name for mood in payload.moods]))
        await self.repo.save(genre, 'moods')
        await self._invalidate(genre_id)
        return self.read_model.model_validate(genre)

    async def delete(self, genre_id: UUID) -> None:
        genre = await self._get_or_raise(genre_id, with_relations=False)
        genre.is_deleted = True
        await self.repo.save(genre)
        await self._invalidate(genre_id)
