from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)
from pydantic_core import PydanticCustomError

from src.schemas.base import IdentifiedRead

SocialHandle = Annotated[str, StringConstraints(min_length=1, max_length=255)]
SocialKey = Annotated[str, StringConstraints(min_length=1, max_length=32)]
Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=64,
        pattern=r'^[a-zA-Z0-9_]+$',
    ),
]

_USER_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'
_PROFILE_ID_EXAMPLE = '3fa85f64-5717-4562-b3fc-2c963f66afa6'

_PROFILE_PAYLOAD_EXAMPLE: dict[str, Any] = {
    'avatar_url': 'https://example.com/avatars/john.png',
    'bio': 'Книжный энтузиаст и коллекционер фантастики',
    'socials': {'telegram': '@john_doe', 'github': 'johndoe'},
}
_PROFILE_READ_EXAMPLE: dict[str, Any] = {'id': _PROFILE_ID_EXAMPLE, **_PROFILE_PAYLOAD_EXAMPLE}
USER_CREATE_EXAMPLES: dict[str, Any] = {
    'full': {
        'summary': 'Полный профиль',
        'value': {
            'username': 'john_doe',
            'email': 'john@example.com',
            'profile': _PROFILE_PAYLOAD_EXAMPLE,
        },
    },
    'minimal': {
        'summary': 'Минимальный профиль',
        'value': {
            'username': 'jane_doe',
            'email': 'jane@example.com',
            'profile': {'bio': 'Любитель научпопа'},
        },
    },
}
USER_UPDATE_EXAMPLES: dict[str, Any] = {
    'email_only': {
        'summary': 'Только email',
        'value': {'email': 'john.doe@example.com'},
    },
    'username_only': {
        'summary': 'Только username',
        'value': {'username': 'john_doe_2'},
    },
    'profile_only': {
        'summary': 'Только профиль',
        'value': {'profile': _PROFILE_PAYLOAD_EXAMPLE},
    },
}

_USER_CREATE_EXAMPLES: list[Any] = [
    example['value'] for example in USER_CREATE_EXAMPLES.values()
]
_USER_UPDATE_EXAMPLES: list[Any] = [
    example['value'] for example in USER_UPDATE_EXAMPLES.values()
]
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


class UserCreate(BaseModel):
    username: Username
    email: EmailStr
    profile: UserProfilePayload

    model_config = ConfigDict(
        json_schema_extra={'examples': _USER_CREATE_EXAMPLES},
    )


class UserUpdate(BaseModel):
    username: Username | None = None
    email: EmailStr | None = None
    profile: UserProfilePayload | None = None

    model_config = ConfigDict(
        json_schema_extra={'examples': _USER_UPDATE_EXAMPLES},
    )

    @model_validator(mode='after')
    def _require_any_field(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError(
                'at_least_one_field',
                'At least one field must be provided',
            )
        return self


class UserRead(IdentifiedRead):
    username: str
    email: EmailStr
    created_at: datetime
    profile: UserProfileRead | None

    model_config = ConfigDict(
        json_schema_extra={'examples': [_USER_READ_EXAMPLE]},
    )
