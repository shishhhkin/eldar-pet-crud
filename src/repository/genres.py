from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.genres import GenreModel
from src.models.moods import MoodModel
from src.repository.base import Repo, active_only


class GenreRepo(Repo[GenreModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, GenreModel)

    async def ensure_moods(self, names: Sequence[str]) -> Sequence[MoodModel]:
        insert_stmt = (
            pg_insert(MoodModel)
            .values([{'name': name} for name in names])
            .on_conflict_do_nothing(
                index_elements=['name'],
                index_where=text('is_deleted = false'),
            )
        )
        await self.session.execute(insert_stmt)
        select_stmt = select(MoodModel).options(active_only()).where(MoodModel.name.in_(names))
        return (await self.session.execute(select_stmt)).scalars().all()
