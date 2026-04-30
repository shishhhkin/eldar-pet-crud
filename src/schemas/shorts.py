from __future__ import annotations

from src.schemas.base import IdentifiedRead


class AuthorShortRead(IdentifiedRead):
    name: str


class BookShortRead(IdentifiedRead):
    title: str


class GenreShortRead(IdentifiedRead):
    name: str
