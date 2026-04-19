from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.book_genres import book_genres

if TYPE_CHECKING:
    from src.models.books import BookModel


class GenreModel(Base):
    __tablename__ = 'genres'

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(128), unique=True, nullable=False)

    books: Mapped[list[BookModel]] = relationship(
        secondary=book_genres,
        back_populates='genres',
    )
