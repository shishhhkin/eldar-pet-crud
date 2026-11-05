import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class BookReservationModel(Base):
    __tablename__ = 'book_reservations'

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    author: Mapped[str] = mapped_column(sa.String(128), nullable=False)
