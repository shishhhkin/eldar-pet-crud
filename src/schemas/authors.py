from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from src.schemas.base import IdentifiedRead

__all__ = [
    'BookPayload',
    'BookShortRead',
    'AuthorBase',
    'AuthorCreate',
    'AuthorUpdate',
    'AuthorRead',
]


class BookPayload(BaseModel):
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]


class BookShortRead(IdentifiedRead):
    title: str


class AuthorBase(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    bio: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
        ]
        | None
    ) = None
    books: list[BookPayload] = Field(default_factory=list)


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(AuthorBase):
    pass


class AuthorRead(IdentifiedRead):
    name: str
    bio: str | None
    books: list[BookShortRead]
