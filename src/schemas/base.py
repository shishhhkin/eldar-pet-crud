from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IdentifiedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
