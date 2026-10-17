from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LibraryMembershipCreate(BaseModel):
    user_id: UUID


class LibraryMembership(BaseModel):
    id: UUID
    user_id: UUID
    number: str = Field(max_length=16)
    issued_at: datetime
    version: int
