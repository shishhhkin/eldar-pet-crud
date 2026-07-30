from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.books import BookModel


class AuthorModel(Base):
    __tablename__ = 'authors'

    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    bio: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    books: Mapped[list[BookModel]] = relationship(
        back_populates='author',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
