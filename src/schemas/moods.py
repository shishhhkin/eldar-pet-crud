from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.base import IdentifiedRead
from src.schemas.examples import MOOD_PAYLOAD_EXAMPLE, MOOD_READ_EXAMPLE
from src.schemas.normalizers import dedup_key

MAX_MOODS_PER_GENRE = 20


class MoodPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={'examples': [MOOD_PAYLOAD_EXAMPLE]},
    )

    @field_validator('name', mode='before')
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return dedup_key(value)


class MoodShortRead(IdentifiedRead):
    name: str

    model_config = ConfigDict(
        json_schema_extra={'examples': [MOOD_READ_EXAMPLE]},
    )


def dedup_moods(moods: Sequence[MoodPayload]) -> list[MoodPayload]:
    unique: dict[str, MoodPayload] = {}
    for mood in moods:
        unique.setdefault(mood.name, mood)
    return list(unique.values())
