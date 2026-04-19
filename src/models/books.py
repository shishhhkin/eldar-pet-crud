from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.book_genres import book_genres

if TYPE_CHECKING:
    from src.models.authors import AuthorModel
    from src.models.genres import GenreModel


class BookModel(Base):
    __tablename__ = 'books'

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    author_id: Mapped[UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey('authors.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
    )

    author: Mapped[AuthorModel] = relationship(back_populates='books')
    genres: Mapped[list[GenreModel]] = relationship(
        secondary=book_genres,
        back_populates='books',
    )
