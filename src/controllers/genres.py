from uuid import UUID

from fastapi import APIRouter, status

from src.schemas.genres import GenreCreate, GenreRead, GenreUpdate
from src.services.genre_service import GenreServiceDep, GenreServiceTxDep

router = APIRouter(prefix='/genres', tags=['genres'])


@router.post('', response_model=GenreRead, status_code=status.HTTP_201_CREATED)
async def create_genre(payload: GenreCreate, service: GenreServiceTxDep) -> GenreRead:
    return await service.create(payload)  # type: ignore[return-value]


@router.get('/{genre_id}', response_model=GenreRead)
async def read_genre(genre_id: UUID, service: GenreServiceDep) -> GenreRead:
    return await service.get(genre_id)  # type: ignore[return-value]


@router.put('/{genre_id}', response_model=GenreRead)
async def update_genre(
    genre_id: UUID, payload: GenreUpdate, service: GenreServiceTxDep
) -> GenreRead:
    return await service.update(genre_id, payload)  # type: ignore[return-value]


@router.delete('/{genre_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_genre(genre_id: UUID, service: GenreServiceTxDep) -> None:
    await service.delete(genre_id)
