from uuid import UUID

from fastapi import APIRouter, Response, status

from src.db import SessionDep, TxSessionDep
from src.schemas.genres import GenreCreate, GenreRead, GenreUpdate
from src.services import genre_service

router = APIRouter(prefix='/genres', tags=['genres'])


@router.post('', response_model=GenreRead, status_code=status.HTTP_201_CREATED)
async def create_genre(payload: GenreCreate, session: TxSessionDep) -> GenreRead:
    return await genre_service.create_genre(session, payload)  # type: ignore[return-value]


@router.get('/{genre_id}', response_model=GenreRead)
async def read_genre(genre_id: UUID, session: SessionDep) -> GenreRead:
    return await genre_service.get_genre(session, genre_id)  # type: ignore[return-value]


@router.put('/{genre_id}', response_model=GenreRead)
async def update_genre(
    genre_id: UUID, payload: GenreUpdate, session: TxSessionDep
) -> GenreRead:
    return await genre_service.update_genre(session, genre_id, payload)  # type: ignore[return-value]


@router.delete('/{genre_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_genre(genre_id: UUID, session: TxSessionDep) -> Response:
    await genre_service.delete_genre(session, genre_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
