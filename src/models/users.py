from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.user_profiles import UserProfileModel


class UserModel(Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    profile: Mapped[UserProfileModel] = relationship(
        back_populates='user',
        uselist=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
