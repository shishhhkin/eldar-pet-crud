from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuthorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    bio: str | None = None


class AuthorUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    bio: str | None = None


class AuthorShortRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class AuthorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    bio: str | None
