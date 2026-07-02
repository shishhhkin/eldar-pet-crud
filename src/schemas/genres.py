from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from src.schemas.base import IdentifiedRead, example_values
from src.schemas.moods import (
    MAX_MOODS_PER_GENRE,
    MOOD_READ_EXAMPLE,
    MoodPayload,
    MoodShortRead,
    dedup_moods,
)
from src.schemas.normalizers import dedup_key, forbid_null

_GENRE_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

GENRE_CREATE_EXAMPLES: dict[str, Any] = {
    'multiple_moods': {
        'summary': 'С несколькими настроениями',
        'value': {
            'name': 'Фэнтези',
            'moods': [{'name': 'Меланхоличное'}, {'name': 'Атмосферное'}],
        },
    },
    'single_mood': {
        'summary': 'С одним настроением',
        'value': {'name': 'Детектив', 'moods': [{'name': 'Напряжённое'}]},
    },
}
GENRE_UPDATE_EXAMPLES: dict[str, Any] = {
    'both': {
        'summary': 'Имя и настроения',
        'value': {'name': 'Фэнтези', 'moods': [{'name': 'Меланхоличное'}]},
    },
    'name_only': {
        'summary': 'Только имя',
        'value': {'name': 'Фэнтези'},
    },
    'moods_only': {
        'summary': 'Только настроения',
        'value': {'moods': [{'name': 'Атмосферное'}]},
    },
}

_GENRE_READ_EXAMPLE: dict[str, Any] = {
    'id': _GENRE_ID_EXAMPLE,
    'name': 'Фэнтези',
    'moods': [MOOD_READ_EXAMPLE],
}


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
        json_schema_extra={'examples': [_GENRE_READ_EXAMPLE]},
    )
