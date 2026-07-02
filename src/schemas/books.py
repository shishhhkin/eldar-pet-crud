from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.base import IdentifiedRead
from src.schemas.normalizers import normalize_text

_BOOK_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_BOOK_PAYLOAD_EXAMPLE: dict[str, Any] = {'title': 'Война и мир'}
BOOK_READ_EXAMPLE: dict[str, Any] = {'id': _BOOK_ID_EXAMPLE, 'title': 'Война и мир'}

MAX_BOOKS_PER_AUTHOR = 10000


class BookPayload(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    model_config = ConfigDict(
        json_schema_extra={'examples': [_BOOK_PAYLOAD_EXAMPLE]},
    )

    @field_validator('title', mode='before')
    @classmethod
    def _normalize_title(cls, value: object) -> object:
        return normalize_text(value)


class BookShortRead(IdentifiedRead):
    title: str

    model_config = ConfigDict(
        json_schema_extra={'examples': [BOOK_READ_EXAMPLE]},
    )
