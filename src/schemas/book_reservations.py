from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.base import IdentifiedRead, example_values
from src.schemas.examples import BOOK_RESERVATION_CREATE_EXAMPLES, BOOK_RESERVATION_READ_EXAMPLE
from src.schemas.normalizers import normalize_text


class BookReservationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={'examples': example_values(BOOK_RESERVATION_CREATE_EXAMPLES)},
    )

    @field_validator('title', 'author', mode='before')
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        return normalize_text(value)


class BookReservationRead(IdentifiedRead):
    title: str
    author: str
    created_at: datetime

    model_config = ConfigDict(
        json_schema_extra={'examples': [BOOK_RESERVATION_READ_EXAMPLE]},
    )


class BookReservationEvent(BaseModel):
    id: UUID
    title: str
    author: str
    reserved_at: datetime
