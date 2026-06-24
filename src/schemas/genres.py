from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from src.schemas.base import IdentifiedRead
from src.schemas.fields import DedupName, NotNull

_GENRE_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_MOOD_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

_MOOD_PAYLOAD_EXAMPLE: dict[str, Any] = {'name': 'Меланхоличное'}
_MOOD_READ_EXAMPLE: dict[str, Any] = {'id': _MOOD_ID_EXAMPLE, 'name': 'Меланхоличное'}

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

_GENRE_CREATE_EXAMPLES: list[Any] = [example['value'] for example in GENRE_CREATE_EXAMPLES.values()]
_GENRE_UPDATE_EXAMPLES: list[Any] = [example['value'] for example in GENRE_UPDATE_EXAMPLES.values()]
_GENRE_READ_EXAMPLE: dict[str, Any] = {
    'id': _GENRE_ID_EXAMPLE,
    'name': 'Фэнтези',
    'moods': [_MOOD_READ_EXAMPLE],
}


class MoodPayload(BaseModel):
    name: DedupName

    model_config = ConfigDict(
        json_schema_extra={'examples': [_MOOD_PAYLOAD_EXAMPLE]},
    )


class MoodShortRead(IdentifiedRead):
    name: str

    model_config = ConfigDict(
        json_schema_extra={'examples': [_MOOD_READ_EXAMPLE]},
    )


def _dedup_moods(moods: Sequence[MoodPayload]) -> list[MoodPayload]:
    unique: dict[str, MoodPayload] = {}
    for mood in moods:
        unique.setdefault(mood.name, mood)
    return list(unique.values())


MoodList = Annotated[list[MoodPayload], Field(min_length=1), AfterValidator(_dedup_moods)]


class GenreCreate(BaseModel):
    name: DedupName
    moods: MoodList

    model_config = ConfigDict(
        json_schema_extra={'examples': _GENRE_CREATE_EXAMPLES},
    )


class GenreUpdate(BaseModel):
    name: NotNull[DedupName] = None
    moods: MoodList | None = None

    model_config = ConfigDict(
        json_schema_extra={'examples': _GENRE_UPDATE_EXAMPLES},
    )

    @model_validator(mode='after')
    def _require_any_field(self) -> Self:
        if self.name is None and self.moods is None:
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
