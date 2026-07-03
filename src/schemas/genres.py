from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from src.schemas.base import IdentifiedRead, example_values
from src.schemas.examples import (
    GENRE_CREATE_EXAMPLES,
    GENRE_READ_EXAMPLE,
    GENRE_UPDATE_EXAMPLES,
)
from src.schemas.moods import (
    MAX_MOODS_PER_GENRE,
    MoodPayload,
    MoodShortRead,
    dedup_moods,
)
from src.schemas.normalizers import dedup_key, forbid_null


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    moods: list[MoodPayload] = Field(min_length=1, max_length=MAX_MOODS_PER_GENRE)

    model_config = ConfigDict(
        json_schema_extra={'examples': example_values(GENRE_CREATE_EXAMPLES)},
    )

    @field_validator('name', mode='before')
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return dedup_key(value)

    @field_validator('moods', mode='after')
    @classmethod
    def _dedup_moods(cls, moods: list[MoodPayload]) -> list[MoodPayload]:
        return dedup_moods(moods)


class GenreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    moods: list[MoodPayload] | None = Field(
        default=None, min_length=1, max_length=MAX_MOODS_PER_GENRE
    )

    model_config = ConfigDict(
        json_schema_extra={'examples': example_values(GENRE_UPDATE_EXAMPLES)},
    )

    @field_validator('name', mode='before')
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return dedup_key(forbid_null(value))

    @field_validator('moods', mode='after')
    @classmethod
    def _dedup_moods(cls, moods: list[MoodPayload] | None) -> list[MoodPayload] | None:
        return dedup_moods(moods) if moods is not None else None

    @model_validator(mode='after')
    def _require_any_field(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError(
                'at_least_one_field',
                'At least one of "name" or "moods" must be provided',
            )
        return self


class GenreRead(IdentifiedRead):
    name: str
    moods: list[MoodShortRead]

    model_config = ConfigDict(
        json_schema_extra={'examples': [GENRE_READ_EXAMPLE]},
    )
