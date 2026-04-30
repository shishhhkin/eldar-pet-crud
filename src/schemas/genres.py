from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from src.schemas.base import IdentifiedRead
from src.schemas.shorts import BookShortRead, GenreShortRead

__all__ = [
    'GenreBase',
    'GenreCreate',
    'GenreUpdate',
    'GenreShortRead',
    'GenreRead',
]


class GenreBase(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    ]


class GenreCreate(GenreBase):
    pass


class GenreUpdate(GenreBase):
    pass


class GenreRead(IdentifiedRead, GenreBase):
    books: list[BookShortRead]
