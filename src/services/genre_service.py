from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.genres import GenreModel
from src.models.moods import MoodModel
from src.repository import Repo
from src.schemas.genres import GenreCreate, GenreUpdate


class GenreService:
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
        genre = GenreModel(**payload.model_dump(exclude={'moods'}))
        genre.moods = await self._get_or_create_moods([mood.name for mood in payload.moods])
        self.repo.add(genre)
        await self.repo.flush()
        await self.repo.refresh(genre, ['moods'])
        return genre

    async def get(self, genre_id: UUID) -> GenreModel:
        return await self.repo.get(genre_id, selectinload(GenreModel.moods))

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreModel:
        genre = await self.repo.get(genre_id, selectinload(GenreModel.moods))
        if payload.name is not None:
            genre.name = payload.name
        if payload.moods is not None:
            genre.moods = await self._get_or_create_moods([mood.name for mood in payload.moods])
        await self.repo.flush()
        await self.repo.refresh(genre, ['moods'])
        return genre

    async def delete(self, genre_id: UUID) -> None:
        genre = await self.repo.get(genre_id)
        genre.is_deleted = True
        await self.repo.flush()
