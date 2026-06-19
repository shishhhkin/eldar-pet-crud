from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.schemas.base import IdentifiedRead
from src.schemas.fields import DedupName

_GENRE_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_MOOD_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

_MOOD_PAYLOAD_EXAMPLE: dict[str, Any] = {'name': 'Меланхоличное'}
_MOOD_READ_EXAMPLE: dict[str, Any] = {'id': _MOOD_ID_EXAMPLE, 'name': 'Меланхоличное'}
_GENRE_PAYLOAD_EXAMPLE: dict[str, Any] = {
    'name': 'Фэнтези',
    'moods': [{'name': 'Меланхоличное'}, {'name': 'Атмосферное'}],
}
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


class GenreBase(BaseModel):
    name: DedupName
    moods: list[MoodPayload] = []

    model_config = ConfigDict(
        json_schema_extra={'examples': [_GENRE_PAYLOAD_EXAMPLE]},
    )


class GenreCreate(GenreBase):
    pass


class GenreUpdate(GenreBase):
    pass


class GenreRead(IdentifiedRead):
    name: str
    moods: list[MoodShortRead]

    model_config = ConfigDict(
        json_schema_extra={'examples': [_GENRE_READ_EXAMPLE]},
    )
