from __future__ import annotations

from pydantic import BaseModel, ConfigDict

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

    model_config = ConfigDict(
        json_schema_extra={'examples': [{'title': 'Война и мир'}]},
    )


class BookShortRead(IdentifiedRead):
    title: str

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6', 'title': 'Война и мир'},
            ],
        },
    )


class AuthorBase(BaseModel):
    name: PersonName
    bio: LongText | None = None
    books: list[BookPayload] = []

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'name': 'Лев Толстой',
                    'bio': 'Русский писатель, классик мировой литературы.',
                    'books': [{'title': 'Война и мир'}, {'title': 'Анна Каренина'}],
                },
            ],
        },
    )


class AuthorCreate(AuthorBase):
    pass


class AuthorUpdate(AuthorBase):
    pass


class AuthorRead(IdentifiedRead):
    name: str
    bio: str | None
    books: list[BookShortRead]

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'name': 'Лев Толстой',
                    'bio': 'Русский писатель, классик мировой литературы.',
                    'books': [
                        {
                            'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                            'title': 'Война и мир',
                        },
                    ],
                },
            ],
        },
    )
