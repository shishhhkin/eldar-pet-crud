from uuid import UUID

from fastapi import APIRouter, Response, status

from src.db import SessionDep, TxSessionDep
from src.schemas.books import BookCreate, BookRead, BookUpdate
from src.services import book_service

router = APIRouter(prefix='/books', tags=['books'])


@router.post('', response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(payload: BookCreate, session: TxSessionDep) -> BookRead:
    return await book_service.create_book(session, payload)  # type: ignore[return-value]


@router.get('/{book_id}', response_model=BookRead)
async def read_book(book_id: UUID, session: SessionDep) -> BookRead:
    return await book_service.get_book(session, book_id)  # type: ignore[return-value]


@router.put('/{book_id}', response_model=BookRead)
async def update_book(
    book_id: UUID, payload: BookUpdate, session: TxSessionDep
) -> BookRead:
    return await book_service.update_book(session, book_id, payload)  # type: ignore[return-value]


@router.delete('/{book_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: UUID, session: TxSessionDep) -> Response:
    await book_service.delete_book(session, book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
