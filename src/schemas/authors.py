from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.base import IdentifiedRead


class AuthorBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    bio: str | None = None


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(AuthorBase):
    pass


class AuthorShortRead(IdentifiedRead):
    name: str


class AuthorRead(IdentifiedRead, AuthorBase):
    pass
