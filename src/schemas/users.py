from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, StringConstraints

from src.schemas.base import IdentifiedRead

SocialHandle = Annotated[str, StringConstraints(min_length=1, max_length=255)]
SocialKey = Annotated[str, StringConstraints(min_length=1, max_length=32)]

_USER_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_PROFILE_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

_PROFILE_PAYLOAD_EXAMPLE: dict[str, Any] = {
    'avatar_url': 'https://example.com/avatars/john.png',
    'bio': 'Книжный энтузиаст и коллекционер фантастики',
    'socials': {'telegram': '@john_doe', 'github': 'johndoe'},
}
_PROFILE_READ_EXAMPLE: dict[str, Any] = {'id': _PROFILE_ID_EXAMPLE, **_PROFILE_PAYLOAD_EXAMPLE}
_USER_PAYLOAD_EXAMPLE: dict[str, Any] = {
    'username': 'john_doe',
    'email': 'john@example.com',
    'profile': _PROFILE_PAYLOAD_EXAMPLE,
}
_USER_READ_EXAMPLE: dict[str, Any] = {
    'id': _USER_ID_EXAMPLE,
    'username': 'john_doe',
    'email': 'john@example.com',
    'created_at': '2026-01-15T10:30:00Z',
    'profile': _PROFILE_READ_EXAMPLE,
}


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

    model_config = ConfigDict(
        json_schema_extra={'examples': [_PROFILE_PAYLOAD_EXAMPLE]},
    )


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

    model_config = ConfigDict(
        json_schema_extra={'examples': [_USER_PAYLOAD_EXAMPLE]},
    )


class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    pass


class UserRead(IdentifiedRead):
    username: str
    email: EmailStr
    created_at: datetime
    profile: UserProfileRead | None

    model_config = ConfigDict(
        json_schema_extra={'examples': [_USER_READ_EXAMPLE]},
    )
