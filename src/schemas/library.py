from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LibraryMembershipCreate(BaseModel):
    user_id: UUID


class LibraryMembership(BaseModel):
    id: UUID
    user_id: UUID
    number: str
    issued_at: datetime
    version: int
