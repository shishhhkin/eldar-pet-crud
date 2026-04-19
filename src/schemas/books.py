from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.authors import AuthorShortRead
from src.schemas.genres import GenreShortRead


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author_id: UUID
    genre_ids: list[UUID] = Field(default_factory=list)


class BookUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author_id: UUID
    genre_ids: list[UUID] = Field(default_factory=list)


class BookRead(BaseModel):
    """FK (author_id) в ответе не светим — отдаём вложенные author и genres."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: AuthorShortRead
    genres: list[GenreShortRead]
