from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserProfilePayload(BaseModel):
    """Входящая часть профиля — поля, которые клиент может задать.

    Поля nullable: позволяет создать пользователя с «пустым» профилем,
    удовлетворяя требование задания (вложенный JSON обязателен).
    """

    avatar_url: str | None = Field(default=None, max_length=512)
    bio: str | None = None
    socials: dict | None = None


class UserProfileRead(BaseModel):
    """Исходящая схема профиля. FK (user_id) наружу не отдаём."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    avatar_url: str | None
    bio: str | None
    socials: dict | None


class UserCreate(BaseModel):
    """POST /users — вся информация во вложенном JSON, как требует задание."""

    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    profile: UserProfilePayload


class UserUpdate(BaseModel):
    """PUT /users/{id} — тот же контракт, что и Create (полная замена)."""

    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    profile: UserProfilePayload


class UserRead(BaseModel):
    """GET /users/{id} — отдаём первичные ключи и вложенный объект, без FK."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    created_at: datetime
    profile: UserProfileRead | None
