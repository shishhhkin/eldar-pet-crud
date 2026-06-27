from uuid import UUID

from sqlalchemy.orm import selectinload

from src.mappers.genres import apply_genre_update, to_genre_model, to_genre_read
from src.models.genres import GenreModel
from src.repository import GenreRepo
from src.schemas.genres import GenreCreate, GenreRead, GenreUpdate
from src.services.base import BaseService


class GenreService(BaseService[GenreModel]):
    repo: GenreRepo

    async def create(self, payload: GenreCreate) -> GenreRead:
        moods = await self.repo.ensure_moods([mood.name for mood in payload.moods])
        genre = to_genre_model(payload, moods)
        await self.repo.save(genre, 'moods')
        return to_genre_read(genre)

    async def get(self, genre_id: UUID) -> GenreRead:
        genre = await self._get_or_raise(genre_id, selectinload(GenreModel.moods))
        return to_genre_read(genre)

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreRead:
        genre = await self._get_or_raise(genre_id, selectinload(GenreModel.moods))
        apply_genre_update(genre, payload)
        if payload.moods is not None:
            genre.moods = list(
                await self.repo.ensure_moods([mood.name for mood in payload.moods])
            )
        await self.repo.save(genre, 'moods')
        return to_genre_read(genre)

    async def delete(self, genre_id: UUID) -> None:
        genre = await self._get_or_raise(genre_id)
        genre.is_deleted = True
        await self.repo.save(genre)
