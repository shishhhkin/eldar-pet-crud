from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.user_profiles import UserProfileModel


class UserModel(Base):
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

    username: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    profile: Mapped[UserProfileModel] = relationship(
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
