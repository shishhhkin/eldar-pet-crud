from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid7

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import AnalyticsMixin, Base

if TYPE_CHECKING:
    from src.models.user_profiles import UserProfileModel


class UserModel(AnalyticsMixin, Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid7)
    username: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)

    profile: Mapped[UserProfileModel] = relationship(
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
