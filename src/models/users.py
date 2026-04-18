# Base вынесен в src/models/base.py — здесь импортируем из единой точки.
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class UserModel(Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(sa.String(255), nullable=False)
