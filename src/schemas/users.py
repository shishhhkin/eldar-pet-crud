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
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from src.schemas.base import IdentifiedRead, example_values
from src.schemas.normalizers import forbid_null, normalize_text

_USERNAME_PATTERN = r'^[a-zA-Z0-9_]+$'

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

_USER_READ_EXAMPLE: dict[str, Any] = {
    'id': _USER_ID_EXAMPLE,
    'username': 'john_doe',
    'email': 'john@example.com',
    'created_at': '2026-01-15T10:30:00Z',
    'profile': _PROFILE_READ_EXAMPLE,
}


class UserProfilePayload(BaseModel):
    avatar_url: HttpUrl | None = None
    bio: str | None = Field(default=None, min_length=1, max_length=2000)
    socials: (
        dict[
            Annotated[str, StringConstraints(min_length=1, max_length=32)],
            Annotated[str, StringConstraints(min_length=1, max_length=255)],
        ]
        | None
    ) = Field(default=None, max_length=32)

    model_config = ConfigDict(
        json_schema_extra={'examples': [_PROFILE_PAYLOAD_EXAMPLE]},
    )

    @field_validator('bio', mode='before')
    @classmethod
    def _normalize_bio(cls, value: object) -> object:
        return normalize_text(value)


class UserProfileRead(IdentifiedRead, UserProfilePayload):
    pass


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=_USERNAME_PATTERN)
    email: EmailStr
    profile: UserProfilePayload

    model_config = ConfigDict(
        json_schema_extra={'examples': example_values(USER_CREATE_EXAMPLES)},
    )

    @field_validator('username', mode='before')
    @classmethod
    def _normalize_username(cls, value: object) -> object:
        return normalize_text(value)


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None, min_length=3, max_length=64, pattern=_USERNAME_PATTERN
    )
    email: EmailStr | None = Field(default=None)
    profile: UserProfilePayload | None = None

    model_config = ConfigDict(
        json_schema_extra={'examples': example_values(USER_UPDATE_EXAMPLES)},
    )

    @field_validator('username', mode='before')
    @classmethod
    def _normalize_username(cls, value: object) -> object:
        return normalize_text(forbid_null(value))

    @field_validator('email', mode='before')
    @classmethod
    def _forbid_null_email(cls, value: object) -> object:
        return forbid_null(value)

    @model_validator(mode='after')
    def _require_any_field(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError(
                'at_least_one_field',
                'At least one of "username", "email" or "profile" must be provided',
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
