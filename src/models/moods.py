from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid7

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import AnalyticsMixin, Base
from src.models.genre_moods import genre_moods

if TYPE_CHECKING:
    from src.models.genres import GenreModel


class MoodModel(AnalyticsMixin, Base):
    __tablename__ = 'moods'
    __table_args__ = (
        sa.Index(
            'uq_moods_name_active',
            'name',
            unique=True,
            postgresql_where=sa.text('is_deleted = false'),
        ),
    )

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    genres: Mapped[list[GenreModel]] = relationship(
        secondary=genre_moods,
        back_populates='moods',
    )
