from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IdentifiedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


def example_values(examples: dict[str, Any]) -> list[Any]:
    return [example['value'] for example in examples.values()]
