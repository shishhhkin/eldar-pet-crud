from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from src.db import SessionDep
from src.schemas.genres import GenreCreate, GenreRead, GenreUpdate
from src.services import genre_service

router = APIRouter(prefix='/genres', tags=['genres'])


@router.post('', response_model=GenreRead, status_code=status.HTTP_201_CREATED)
async def create_genre(payload: GenreCreate, session: SessionDep) -> GenreRead:
    async with session.begin():
        genre = await genre_service.create_genre(session, payload)
    return GenreRead.model_validate(genre)


@router.get('/{genre_id}', response_model=GenreRead)
async def read_genre(genre_id: UUID, session: SessionDep) -> GenreRead:
    genre = await genre_service.get_genre(session, genre_id)
    if genre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Genre not found')
    return GenreRead.model_validate(genre)


@router.put('/{genre_id}', response_model=GenreRead)
async def update_genre(
    genre_id: UUID, payload: GenreUpdate, session: SessionDep
) -> GenreRead:
    async with session.begin():
        genre = await genre_service.update_genre(session, genre_id, payload)
    if genre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Genre not found')
    return GenreRead.model_validate(genre)


@router.delete('/{genre_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_genre(genre_id: UUID, session: SessionDep) -> Response:
    async with session.begin():
        deleted = await genre_service.delete_genre(session, genre_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Genre not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)
