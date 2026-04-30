from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from src.schemas.base import IdentifiedRead
from src.schemas.shorts import AuthorShortRead, BookShortRead

__all__ = [
    'AuthorBase',
    'AuthorCreate',
    'AuthorUpdate',
    'AuthorShortRead',
    'AuthorRead',
]


class AuthorBase(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    bio: str | None = Field(default=None, max_length=2000)


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(AuthorBase):
    pass


class AuthorRead(IdentifiedRead, AuthorBase):
    books: list[BookShortRead]
