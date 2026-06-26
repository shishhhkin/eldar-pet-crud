from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from src.schemas.base import IdentifiedRead
from src.schemas.fields import DedupName

_MOOD_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_MOOD_PAYLOAD_EXAMPLE: dict[str, Any] = {'name': 'Меланхоличное'}
_MOOD_READ_EXAMPLE: dict[str, Any] = {'id': _MOOD_ID_EXAMPLE, 'name': 'Меланхоличное'}

_MAX_MOODS_PER_GENRE = 20


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


def _dedup_moods(moods: Sequence[MoodPayload]) -> list[MoodPayload]:
    unique: dict[str, MoodPayload] = {}
    for mood in moods:
        unique.setdefault(mood.name, mood)
    return list(unique.values())


MoodList = Annotated[
    list[MoodPayload],
    Field(min_length=1, max_length=_MAX_MOODS_PER_GENRE),
    AfterValidator(_dedup_moods),
]
