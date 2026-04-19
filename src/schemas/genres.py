from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class GenreUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class GenreShortRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
