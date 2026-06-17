from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from src.schemas.base import IdentifiedRead

__all__ = [
    'MoodPayload',
    'MoodShortRead',
    'GenreBase',
    'GenreCreate',
    'GenreUpdate',
    'GenreRead',
]


class MoodPayload(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    ]


class MoodShortRead(IdentifiedRead):
    name: str


class GenreBase(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    ]
    moods: list[MoodPayload] = Field(default_factory=list)


class GenreCreate(GenreBase):
    pass


class GenreUpdate(GenreBase):
    pass


class GenreRead(IdentifiedRead):
    name: str
    moods: list[MoodShortRead]
