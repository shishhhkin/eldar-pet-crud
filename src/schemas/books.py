from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.base import IdentifiedRead
from src.schemas.fields import ShortText

_BOOK_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_BOOK_PAYLOAD_EXAMPLE: dict[str, Any] = {'title': 'Война и мир'}
_BOOK_READ_EXAMPLE: dict[str, Any] = {'id': _BOOK_ID_EXAMPLE, 'title': 'Война и мир'}

_MAX_BOOKS_PER_AUTHOR = 10000


class BookPayload(BaseModel):
    title: ShortText

    model_config = ConfigDict(
        json_schema_extra={'examples': [_BOOK_PAYLOAD_EXAMPLE]},
    )


BookList = Annotated[list[BookPayload], Field(max_length=_MAX_BOOKS_PER_AUTHOR)]


class BookShortRead(IdentifiedRead):
    title: str

    model_config = ConfigDict(
        json_schema_extra={'examples': [_BOOK_READ_EXAMPLE]},
    )
