from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid7

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import AnalyticsMixin, Base

if TYPE_CHECKING:
    from src.models.books import BookModel


class AuthorModel(AnalyticsMixin, Base):
    __tablename__ = 'authors'

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    bio: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    books: Mapped[list[BookModel]] = relationship(
        back_populates='author',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
