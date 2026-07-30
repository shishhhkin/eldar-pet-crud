from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from src.dependencies import GenreServiceDep, GenreServiceTxDep
from src.schemas.errors import (
    CREATE_RESPONSES,
    DELETE_RESPONSES,
    READ_RESPONSES,
    UPDATE_RESPONSES,
)
from src.schemas.examples import GENRE_CREATE_EXAMPLES, GENRE_UPDATE_EXAMPLES
from src.schemas.genres import GenreCreate, GenreRead, GenreUpdate

router = APIRouter(prefix='/genres', tags=['genres'])


@router.post(
    '',
    response_model=GenreRead,
    status_code=status.HTTP_201_CREATED,
    responses=CREATE_RESPONSES,
)
async def create_genre(
    payload: Annotated[GenreCreate, Body(openapi_examples=GENRE_CREATE_EXAMPLES)],
    service: GenreServiceTxDep,
) -> GenreRead:
    return await service.create(payload)


@router.get('/{genre_id}', response_model=GenreRead, responses=READ_RESPONSES)
async def read_genre(genre_id: UUID, service: GenreServiceDep) -> GenreRead:
    return await service.get(genre_id)


@router.patch('/{genre_id}', response_model=GenreRead, responses=UPDATE_RESPONSES)
async def update_genre(
    genre_id: UUID,
    payload: Annotated[GenreUpdate, Body(openapi_examples=GENRE_UPDATE_EXAMPLES)],
    service: GenreServiceTxDep,
) -> GenreRead:
    return await service.update(genre_id, payload)


@router.delete(
    '/{genre_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=DELETE_RESPONSES,
)
async def delete_genre(genre_id: UUID, service: GenreServiceTxDep) -> None:
    await service.delete(genre_id)
