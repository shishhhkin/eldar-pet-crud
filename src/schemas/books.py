from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from src.schemas.base import IdentifiedRead
from src.schemas.shorts import AuthorShortRead, BookShortRead, GenreShortRead

__all__ = [
    'BookBase',
    'BookCreate',
    'BookUpdate',
    'BookShortRead',
    'BookRead',
]


class BookBase(BaseModel):
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    author_id: UUID
    genre_ids: list[UUID] = Field(default_factory=list)


class BookCreate(BookBase):
    pass


class BookUpdate(BookBase):
    pass


class BookRead(IdentifiedRead):
    title: str
    author: AuthorShortRead
    genres: list[GenreShortRead]
