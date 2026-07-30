from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self

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
from src.schemas.examples import (
    PROFILE_PAYLOAD_EXAMPLE,
    USER_CREATE_EXAMPLES,
    USER_READ_EXAMPLE,
    USER_UPDATE_EXAMPLES,
)
from src.schemas.normalizers import forbid_null, normalize_text

_USERNAME_PATTERN = r'^[a-zA-Z0-9_]+$'


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
        json_schema_extra={'examples': [PROFILE_PAYLOAD_EXAMPLE]},
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
        json_schema_extra={'examples': [USER_READ_EXAMPLE]},
    )
