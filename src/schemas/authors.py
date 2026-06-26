from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_core import PydanticCustomError

from src.schemas.base import IdentifiedRead
from src.schemas.books import _BOOK_READ_EXAMPLE, BookList, BookShortRead
from src.schemas.fields import LongText, NotNull, PersonName

_AUTHOR_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

AUTHOR_CREATE_EXAMPLES: dict[str, Any] = {
    'with_books': {
        'summary': 'С книгами',
        'value': {
            'name': 'Лев Толстой',
            'bio': 'Русский писатель, классик мировой литературы.',
            'books': [{'title': 'Война и мир'}, {'title': 'Анна Каренина'}],
        },
    },
    'without_books': {
        'summary': 'Без книг',
        'value': {
            'name': 'Лев Толстой',
            'bio': 'Русский писатель, классик мировой литературы.',
        },
    },
}
AUTHOR_UPDATE_EXAMPLES: dict[str, Any] = {
    'name_and_bio': {
        'summary': 'Имя и био',
        'value': {
            'name': 'Лев Николаевич Толстой',
            'bio': 'Русский писатель, классик мировой литературы.',
        },
    },
    'bio_only': {
        'summary': 'Только био',
        'value': {'bio': 'Граф, писатель и мыслитель.'},
    },
    'books_only': {
        'summary': 'Только книги (замена)',
        'value': {'books': [{'title': 'Воскресение'}]},
    },
}

_AUTHOR_CREATE_EXAMPLES: list[Any] = [
    example['value'] for example in AUTHOR_CREATE_EXAMPLES.values()
]
_AUTHOR_UPDATE_EXAMPLES: list[Any] = [
    example['value'] for example in AUTHOR_UPDATE_EXAMPLES.values()
]
_AUTHOR_READ_EXAMPLE: dict[str, Any] = {
    'id': _AUTHOR_ID_EXAMPLE,
    'name': 'Лев Толстой',
    'bio': 'Русский писатель, классик мировой литературы.',
    'books': [_BOOK_READ_EXAMPLE],
}


class AuthorCreate(BaseModel):
    name: PersonName
    bio: LongText | None = None
    books: BookList = []

    model_config = ConfigDict(
        json_schema_extra={'examples': _AUTHOR_CREATE_EXAMPLES},
    )


class AuthorUpdate(BaseModel):
    name: NotNull[PersonName] = None
    bio: LongText | None = None
    books: BookList | None = None

    model_config = ConfigDict(
        json_schema_extra={'examples': _AUTHOR_UPDATE_EXAMPLES},
    )

    @model_validator(mode='after')
    def _require_any_field(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError(
                'at_least_one_field',
                'At least one field must be provided',
            )
        return self


class AuthorRead(IdentifiedRead):
    name: str
    bio: str | None
    books: list[BookShortRead]

    model_config = ConfigDict(
        json_schema_extra={'examples': [_AUTHOR_READ_EXAMPLE]},
    )
