from typing import Annotated

from fastapi import APIRouter, Body, status

from src.dependencies.book_reservations import BookReservationServiceTxDep
from src.schemas.book_reservations import BookReservationCreate, BookReservationRead
from src.schemas.errors import BODY_VALIDATION_RESPONSES
from src.schemas.examples import BOOK_RESERVATION_CREATE_EXAMPLES

router = APIRouter(prefix='/book-reservations', tags=['book-reservations'])


@router.post(
    '',
    response_model=BookReservationRead,
    status_code=status.HTTP_201_CREATED,
    responses=BODY_VALIDATION_RESPONSES,
)
async def create_book_reservation(
    payload: Annotated[
        BookReservationCreate, Body(openapi_examples=BOOK_RESERVATION_CREATE_EXAMPLES)
    ],
    service: BookReservationServiceTxDep,
) -> BookReservationRead:
    return await service.create(payload)
