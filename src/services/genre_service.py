from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.mappers.genres import apply_genre_update, to_genre_model
from src.models.genres import GenreModel
from src.models.moods import MoodModel
from src.repository import Repo
from src.schemas.genres import GenreCreate, GenreUpdate
from src.services.base import BaseService


class GenreService(BaseService[GenreModel]):
    def __init__(self, session: AsyncSession) -> None:
        self.repo = Repo(session, GenreModel)
        self.mood_repo = Repo(session, MoodModel)

    async def _get_or_create_moods(self, names: list[str]) -> list[MoodModel]:
        if not names:
            return []
        await self.mood_repo.insert_ignoring_conflicts(
            [{'name': name} for name in names],
            index_elements=['name'],
        )
        stmt = self.mood_repo.select().where(MoodModel.name.in_(names))
        return list(await self.mood_repo.scalars(stmt))

    async def create(self, payload: GenreCreate) -> GenreModel:
        moods = await self._get_or_create_moods([mood.name for mood in payload.moods])
        genre = to_genre_model(payload, moods)
        self.repo.add(genre)
        await self.repo.flush()
        await self.repo.refresh(genre, ['moods'])
        return genre

    async def get(self, genre_id: UUID) -> GenreModel:
        return await self._get_or_raise(genre_id, selectinload(GenreModel.moods))

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreModel:
        genre = await self._get_or_raise(genre_id, selectinload(GenreModel.moods))
        moods = (
            await self._get_or_create_moods([mood.name for mood in payload.moods])
            if payload.moods is not None
            else None
        )
        apply_genre_update(genre, payload, moods)
        await self.repo.flush()
        await self.repo.refresh(genre, ['moods'])
        return genre

    async def delete(self, genre_id: UUID) -> None:
        genre = await self._get_or_raise(genre_id)
        genre.is_deleted = True
        await self.repo.flush()
