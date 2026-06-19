from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.schemas.base import IdentifiedRead
from src.schemas.fields import LongText, PersonName, ShortText

_AUTHOR_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_BOOK_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

_BOOK_PAYLOAD_EXAMPLE: dict[str, Any] = {'title': 'Война и мир'}
_BOOK_READ_EXAMPLE: dict[str, Any] = {'id': _BOOK_ID_EXAMPLE, 'title': 'Война и мир'}
_AUTHOR_PAYLOAD_EXAMPLE: dict[str, Any] = {
    'name': 'Лев Толстой',
    'bio': 'Русский писатель, классик мировой литературы.',
    'books': [{'title': 'Война и мир'}, {'title': 'Анна Каренина'}],
}
_AUTHOR_READ_EXAMPLE: dict[str, Any] = {
    'id': _AUTHOR_ID_EXAMPLE,
    'name': 'Лев Толстой',
    'bio': 'Русский писатель, классик мировой литературы.',
    'books': [_BOOK_READ_EXAMPLE],
}


class BookPayload(BaseModel):
    title: ShortText

    model_config = ConfigDict(
        json_schema_extra={'examples': [_BOOK_PAYLOAD_EXAMPLE]},
    )


class BookShortRead(IdentifiedRead):
    title: str

    model_config = ConfigDict(
        json_schema_extra={'examples': [_BOOK_READ_EXAMPLE]},
    )


class AuthorBase(BaseModel):
    name: PersonName
    bio: LongText | None = None
    books: list[BookPayload] = []

    model_config = ConfigDict(
        json_schema_extra={'examples': [_AUTHOR_PAYLOAD_EXAMPLE]},
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
        json_schema_extra={'examples': [_AUTHOR_READ_EXAMPLE]},
    )
