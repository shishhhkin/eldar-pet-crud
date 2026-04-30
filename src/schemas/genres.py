from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.base import IdentifiedRead


class GenreBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class GenreCreate(GenreBase):
    pass


class GenreUpdate(GenreBase):
    pass


class GenreRead(IdentifiedRead):
    name: str
