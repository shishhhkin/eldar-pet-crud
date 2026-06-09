from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid7

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import AnalyticsMixin, Base
from src.models.book_genres import book_genres

if TYPE_CHECKING:
    from src.models.books import BookModel


class GenreModel(AnalyticsMixin, Base):
    __tablename__ = 'genres'
    __table_args__ = (
        sa.Index(
            'uq_genres_name_active',
            'name',
            unique=True,
            postgresql_where=sa.text('is_deleted = false'),
        ),
    )

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    books: Mapped[list[BookModel]] = relationship(
        secondary=book_genres,
        back_populates='genres',
    )
