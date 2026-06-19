from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.genre_moods import genre_moods

if TYPE_CHECKING:
    from src.models.moods import MoodModel


class GenreModel(Base):
    __tablename__ = 'genres'
    __table_args__ = (
        sa.Index(
            'uq_genres_name_active',
            'name',
            unique=True,
            postgresql_where=sa.text('is_deleted = false'),
        ),
    )

    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    moods: Mapped[list[MoodModel]] = relationship(
        secondary=genre_moods,
        back_populates='genres',
    )
