from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.base import IdentifiedRead
from src.schemas.examples import BOOK_PAYLOAD_EXAMPLE, BOOK_READ_EXAMPLE
from src.schemas.normalizers import normalize_text

MAX_BOOKS_PER_AUTHOR = 10000


class BookPayload(BaseModel):
    title: str = Field(min_length=1, max_length=255)

    model_config = ConfigDict(
        json_schema_extra={'examples': [BOOK_PAYLOAD_EXAMPLE]},
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
