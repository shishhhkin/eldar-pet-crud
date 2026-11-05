import logging

from src.mappers.book_reservations import (
    to_book_reservation_event,
    to_book_reservation_model,
    to_book_reservation_read,
)
from src.repository import BookReservationOutboxRepo, BookReservationRepo
from src.schemas.book_reservations import BookReservationCreate, BookReservationRead

logger = logging.getLogger(__name__)


class BookReservationService:
    def __init__(self, repo: BookReservationRepo, outbox: BookReservationOutboxRepo) -> None:
        self.repo = repo
        self.outbox = outbox

    async def create(self, payload: BookReservationCreate) -> BookReservationRead:
        reservation = await self.repo.save(to_book_reservation_model(payload), 'created_at')
        await self.outbox.add(to_book_reservation_event(reservation))
        logger.info('book reservation created: id=%s', reservation.id)
        return to_book_reservation_read(reservation)
