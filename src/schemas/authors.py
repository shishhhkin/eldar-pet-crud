from __future__ import annotations

import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from src.schemas.base import IdentifiedRead, example_values
from src.schemas.books import MAX_BOOKS_PER_AUTHOR, BookPayload, BookShortRead
from src.schemas.examples import (
    AUTHOR_CREATE_EXAMPLES,
    AUTHOR_READ_EXAMPLE,
    AUTHOR_UPDATE_EXAMPLES,
)
from src.schemas.normalizers import clean_text, forbid_null, normalize_text

_WORD_START_RE = re.compile(r'\b\w')


def _person_name(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned = clean_text(value).casefold()
    return _WORD_START_RE.sub(lambda match: match.group().upper(), cleaned)


class AuthorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    bio: str | None = Field(default=None, min_length=1, max_length=2000)
    books: list[BookPayload] = Field(default=[], max_length=MAX_BOOKS_PER_AUTHOR)

    model_config = ConfigDict(
        json_schema_extra={'examples': example_values(AUTHOR_CREATE_EXAMPLES)},
    )

    @field_validator('name', mode='before')
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return _person_name(value)

    @field_validator('bio', mode='before')
    @classmethod
    def _normalize_bio(cls, value: object) -> object:
        return normalize_text(value)


class AuthorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    bio: str | None = Field(default=None, min_length=1, max_length=2000)
    books: list[BookPayload] | None = Field(default=None, max_length=MAX_BOOKS_PER_AUTHOR)

    model_config = ConfigDict(
        json_schema_extra={'examples': example_values(AUTHOR_UPDATE_EXAMPLES)},
    )

    @field_validator('name', mode='before')
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return _person_name(forbid_null(value))

    @field_validator('bio', mode='before')
    @classmethod
    def _normalize_bio(cls, value: object) -> object:
        return normalize_text(value)

    @model_validator(mode='after')
    def _require_any_field(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError(
                'at_least_one_field',
                'At least one of "name", "bio" or "books" must be provided',
            )
        return self


class AuthorRead(IdentifiedRead):
    name: str
    bio: str | None
    books: list[BookShortRead]

    model_config = ConfigDict(
        json_schema_extra={'examples': [AUTHOR_READ_EXAMPLE]},
    )
