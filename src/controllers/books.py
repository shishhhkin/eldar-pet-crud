from uuid import UUID

from fastapi import APIRouter, status

from src.schemas.books import BookCreate, BookRead, BookUpdate
from src.services.deps import BookServiceDep, BookServiceTxDep

router = APIRouter(prefix='/books', tags=['books'])


@router.post('', response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(payload: BookCreate, service: BookServiceTxDep) -> BookRead:
    return await service.create(payload)  # type: ignore[return-value]


@router.get('/{book_id}', response_model=BookRead)
async def read_book(book_id: UUID, service: BookServiceDep) -> BookRead:
    return await service.get(book_id)  # type: ignore[return-value]


@router.put('/{book_id}', response_model=BookRead)
async def update_book(book_id: UUID, payload: BookUpdate, service: BookServiceTxDep) -> BookRead:
    return await service.update(book_id, payload)  # type: ignore[return-value]


@router.delete('/{book_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: UUID, service: BookServiceTxDep) -> None:
    await service.delete(book_id)
