from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, StringConstraints

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

    model_config = ConfigDict(
        json_schema_extra={
            'examples': [
                {
                    'avatar_url': 'https://example.com/avatars/john.png',
                    'bio': 'Книжный энтузиаст и коллекционер фантастики',
                    'socials': {'telegram': '@john_doe', 'github': 'johndoe'},
                },
            ],
        },
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
        json_schema_extra={
            'examples': [
                {
                    'username': 'john_doe',
                    'email': 'john@example.com',
                    'profile': {
                        'avatar_url': 'https://example.com/avatars/john.png',
                        'bio': 'Книжный энтузиаст и коллекционер фантастики',
                        'socials': {'telegram': '@john_doe', 'github': 'johndoe'},
                    },
                },
            ],
        },
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
        json_schema_extra={
            'examples': [
                {
                    'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                    'username': 'john_doe',
                    'email': 'john@example.com',
                    'created_at': '2026-01-15T10:30:00Z',
                    'profile': {
                        'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
                        'avatar_url': 'https://example.com/avatars/john.png',
                        'bio': 'Книжный энтузиаст и коллекционер фантастики',
                        'socials': {'telegram': '@john_doe', 'github': 'johndoe'},
                    },
                },
            ],
        },
    )
