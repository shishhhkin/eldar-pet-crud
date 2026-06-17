from __future__ import annotations

from pydantic import BaseModel

from src.schemas.base import IdentifiedRead
from src.schemas.fields import LongText, PersonName, ShortText

__all__ = [
    'BookPayload',
    'BookShortRead',
    'AuthorBase',
    'AuthorCreate',
    'AuthorUpdate',
    'AuthorRead',
]


class BookPayload(BaseModel):
    title: ShortText


class BookShortRead(IdentifiedRead):
    title: str


class AuthorBase(BaseModel):
    name: PersonName
    bio: LongText | None = None
    books: list[BookPayload] = []


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(AuthorBase):
    pass


class AuthorRead(IdentifiedRead):
    name: str
    bio: str | None
    books: list[BookShortRead]
