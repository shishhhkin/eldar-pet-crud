from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.authors import AuthorShortRead
from src.schemas.base import IdentifiedRead
from src.schemas.genres import GenreRead


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author_id: UUID
    genre_ids: list[UUID] = Field(default_factory=list)


class BookCreate(BookBase):
    pass


class BookUpdate(BookBase):
    pass


class BookRead(IdentifiedRead):
    title: str
    author: AuthorShortRead
    genres: list[GenreRead]
