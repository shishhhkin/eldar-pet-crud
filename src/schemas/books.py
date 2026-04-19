from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.authors import AuthorShortRead


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author_id: UUID


class BookUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author_id: UUID


class BookRead(BaseModel):
    """FK (author_id) в ответе не светим — отдаём вложенный author."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    author: AuthorShortRead
