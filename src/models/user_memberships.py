from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.users import UserModel


class UserMembershipModel(Base):
    __tablename__ = 'user_memberships'

    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        unique=True,
        nullable=False,
    )
    number: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    user: Mapped[UserModel] = relationship(back_populates='membership')
