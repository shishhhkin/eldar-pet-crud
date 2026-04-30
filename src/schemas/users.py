from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from src.schemas.base import IdentifiedRead


class UserProfilePayload(BaseModel):
    avatar_url: str | None = Field(default=None, max_length=512)
    bio: str | None = None
    socials: dict | None = None


class UserProfileRead(IdentifiedRead, UserProfilePayload):
    pass


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    profile: UserProfilePayload


class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    pass


class UserRead(IdentifiedRead):
    username: str
    email: EmailStr
    created_at: datetime
    profile: UserProfileRead | None
