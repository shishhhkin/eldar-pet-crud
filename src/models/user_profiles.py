from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid7

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import AnalyticsMixin, Base

if TYPE_CHECKING:
    from src.models.users import UserModel


class UserProfileModel(AnalyticsMixin, Base):
    __tablename__ = 'user_profiles'

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid7)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        unique=True,
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    bio: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    socials: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped[UserModel] = relationship(back_populates='profile')
