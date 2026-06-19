from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ObjectNotFoundError
from src.models.genres import GenreModel
from src.models.moods import MoodModel
from src.schemas.genres import GenreCreate, GenreUpdate


class GenreService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_with_moods(self, genre_id: UUID) -> GenreModel:
        stmt = (
            select(GenreModel)
            .where(GenreModel.id == genre_id)
            .options(selectinload(GenreModel.moods))
        )
        genre = (await self.session.execute(stmt)).scalar_one_or_none()
        if genre is None:
            raise ObjectNotFoundError(GenreModel, genre_id)
        return genre

    async def _resolve_moods(self, names: list[str]) -> list[MoodModel]:
        if not names:
            return []
        unique_names = list(dict.fromkeys(names))
        stmt = select(MoodModel).where(MoodModel.name.in_(unique_names))
        existing = {mood.name: mood for mood in (await self.session.execute(stmt)).scalars().all()}
        new_moods = [MoodModel(name=name) for name in unique_names if name not in existing]
        self.session.add_all(new_moods)
        existing.update({mood.name: mood for mood in new_moods})
        return [existing[name] for name in unique_names]

    async def create(self, payload: GenreCreate) -> GenreModel:
        genre = GenreModel(**payload.model_dump(exclude={'moods'}))
        genre.moods = await self._resolve_moods([mood.name for mood in payload.moods])
        self.session.add(genre)
        await self.session.flush()
        await self.session.refresh(genre, attribute_names=['moods'])
        return genre

    async def get(self, genre_id: UUID) -> GenreModel:
        return await self._get_with_moods(genre_id)

    async def update(self, genre_id: UUID, payload: GenreUpdate) -> GenreModel:
        genre = await self._get_with_moods(genre_id)
        if payload.name is not None:
            genre.name = payload.name
        if payload.moods is not None:
            genre.moods = await self._resolve_moods([mood.name for mood in payload.moods])
        await self.session.flush()
        await self.session.refresh(genre, attribute_names=['moods'])
        return genre

    async def delete(self, genre_id: UUID) -> None:
        genre = await self.session.get(GenreModel, genre_id)
        if genre is None:
            raise ObjectNotFoundError(GenreModel, genre_id)
        genre.is_deleted = True
        await self.session.flush()
