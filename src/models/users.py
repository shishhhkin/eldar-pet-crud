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
    __table_args__ = (
        sa.Index(
            'uq_users_username_active',
            'username',
            unique=True,
            postgresql_where=sa.text('is_deleted = false'),
        ),
        sa.Index(
            'uq_users_email_active',
            'email',
            unique=True,
            postgresql_where=sa.text('is_deleted = false'),
        ),
    )

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid7)
    username: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    profile: Mapped[UserProfileModel] = relationship(
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
