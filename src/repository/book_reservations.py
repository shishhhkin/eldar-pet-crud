from sqlalchemy.ext.asyncio import AsyncSession

from src.models.book_reservations import BookReservationModel
from src.repository.base import Repo


class BookReservationRepo(Repo[BookReservationModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BookReservationModel)
