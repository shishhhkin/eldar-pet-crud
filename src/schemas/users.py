from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfilePayload(BaseModel):
    avatar_url: str | None = Field(default=None, max_length=512)
    bio: str | None = None
    socials: dict | None = None


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    avatar_url: str | None
    bio: str | None
    socials: dict | None


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    profile: UserProfilePayload


class UserUpdate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    profile: UserProfilePayload


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    created_at: datetime
    profile: UserProfileRead | None
