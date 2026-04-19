from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from src.db import SessionDep
from src.schemas.books import BookCreate, BookRead, BookUpdate
from src.services import book_service

router = APIRouter(prefix='/books', tags=['books'])


@router.post('', response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(payload: BookCreate, session: SessionDep) -> BookRead:
    try:
        async with session.begin():
            book = await book_service.create_book(session, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return BookRead.model_validate(book)


@router.get('/{book_id}', response_model=BookRead)
async def read_book(book_id: UUID, session: SessionDep) -> BookRead:
    book = await book_service.get_book(session, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Book not found')
    return BookRead.model_validate(book)


@router.put('/{book_id}', response_model=BookRead)
async def update_book(book_id: UUID, payload: BookUpdate, session: SessionDep) -> BookRead:
    try:
        async with session.begin():
            book = await book_service.update_book(session, book_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Book not found')
    return BookRead.model_validate(book)


@router.delete('/{book_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: UUID, session: SessionDep) -> Response:
    async with session.begin():
        deleted = await book_service.delete_book(session, book_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Book not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)
