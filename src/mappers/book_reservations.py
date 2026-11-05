from src.models.book_reservations import BookReservationModel
from src.schemas.book_reservations import (
    BookReservationCreate,
    BookReservationEvent,
    BookReservationRead,
)


def to_book_reservation_model(payload: BookReservationCreate) -> BookReservationModel:
    return BookReservationModel(**payload.model_dump())


def to_book_reservation_read(reservation: BookReservationModel) -> BookReservationRead:
    return BookReservationRead.model_validate(reservation)


def to_book_reservation_event(reservation: BookReservationModel) -> BookReservationEvent:
    return BookReservationEvent(
        id=reservation.id,
        title=reservation.title,
        author=reservation.author,
        reserved_at=reservation.created_at,
    )
