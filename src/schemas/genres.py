from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.schemas.base import IdentifiedRead
from src.schemas.fields import DedupName

__all__ = [
    'MoodPayload',
    'MoodShortRead',
    'GenreBase',
    'GenreCreate',
    'GenreUpdate',
    'GenreRead',
]


class MoodPayload(BaseModel):
    name: DedupName

    model_config = ConfigDict(
        json_schema_extra={'examples': [{'name': 'Меланхоличное'}]},
    )


class MoodShortRead(IdentifiedRead):
    name: str

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6', 'name': 'Меланхоличное'},
            ],
        },
    )


class GenreBase(BaseModel):
    name: DedupName
    moods: list[MoodPayload] = []

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'name': 'Фэнтези',
                    'moods': [{'name': 'Меланхоличное'}, {'name': 'Атмосферное'}],
                },
            ],
        },
    )


class GenreCreate(GenreBase):
    pass


class GenreUpdate(GenreBase):
    pass


class GenreRead(IdentifiedRead):
    name: str
    moods: list[MoodShortRead]

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'name': 'Фэнтези',
                    'moods': [
                        {
                            'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                            'name': 'Меланхоличное',
                        },
                    ],
                },
            ],
        },
    )
