from __future__ import annotations

from pydantic import BaseModel

from src.schemas.base import IdentifiedRead
from src.schemas.fields import DedupName

__all__ = [
    'MoodPayload',
    'MoodShortRead',
    'GenreBase',
    'GenreCreate',
    'GenreUpdate',
    'GenreRead',
]


class MoodPayload(BaseModel):
    name: DedupName


class MoodShortRead(IdentifiedRead):
    name: str


class GenreBase(BaseModel):
    name: DedupName
    moods: list[MoodPayload] = []


class GenreCreate(GenreBase):
    pass


class GenreUpdate(GenreBase):
    pass


class GenreRead(IdentifiedRead):
    name: str
    moods: list[MoodShortRead]
