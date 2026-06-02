from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, HttpUrl, StringConstraints

from src.schemas.base import IdentifiedRead

SocialHandle = Annotated[str, StringConstraints(min_length=1, max_length=255)]
SocialKey = Annotated[str, StringConstraints(min_length=1, max_length=32)]


class UserProfilePayload(BaseModel):
    avatar_url: HttpUrl | None = None
    bio: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
        ]
        | None
    ) = None
    socials: dict[SocialKey, SocialHandle] | None = Field(default=None, max_length=32)


class UserProfileRead(IdentifiedRead, UserProfilePayload):
    pass


class UserBase(BaseModel):
    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=64,
            pattern=r'^[a-zA-Z0-9_]+$',
        ),
    ]
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
