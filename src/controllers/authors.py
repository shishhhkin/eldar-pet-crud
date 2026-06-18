from uuid import UUID

from fastapi import APIRouter, status

from src.dependencies import AuthorServiceDep, AuthorServiceTxDep
from src.schemas.authors import AuthorCreate, AuthorRead, AuthorUpdate
from src.schemas.errors import (
    CREATE_RESPONSES,
    DELETE_RESPONSES,
    READ_RESPONSES,
    UPDATE_RESPONSES,
)

router = APIRouter(prefix='/authors', tags=['authors'])


@router.post(
    '',
    response_model=AuthorRead,
    status_code=status.HTTP_201_CREATED,
    responses=CREATE_RESPONSES,
)
async def create_author(payload: AuthorCreate, service: AuthorServiceTxDep) -> AuthorRead:
    return await service.create(payload)  # type: ignore[return-value]


@router.get('/{author_id}', response_model=AuthorRead, responses=READ_RESPONSES)
async def read_author(author_id: UUID, service: AuthorServiceDep) -> AuthorRead:
    return await service.get(author_id)  # type: ignore[return-value]


@router.put('/{author_id}', response_model=AuthorRead, responses=UPDATE_RESPONSES)
async def update_author(
    author_id: UUID, payload: AuthorUpdate, service: AuthorServiceTxDep
) -> AuthorRead:
    return await service.update(author_id, payload)  # type: ignore[return-value]


@router.delete(
    '/{author_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=DELETE_RESPONSES,
)
async def delete_author(author_id: UUID, service: AuthorServiceTxDep) -> None:
    await service.delete(author_id)
