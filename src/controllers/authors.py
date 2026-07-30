from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from src.dependencies import AuthorServiceDep, AuthorServiceTxDep
from src.schemas.authors import AuthorCreate, AuthorRead, AuthorUpdate
from src.schemas.errors import (
    CREATE_RESPONSES,
    DELETE_RESPONSES,
    READ_RESPONSES,
    UPDATE_RESPONSES,
)
from src.schemas.examples import AUTHOR_CREATE_EXAMPLES, AUTHOR_UPDATE_EXAMPLES

router = APIRouter(prefix='/authors', tags=['authors'])


@router.post(
    '',
    response_model=AuthorRead,
    status_code=status.HTTP_201_CREATED,
    responses=CREATE_RESPONSES,
)
async def create_author(
    payload: Annotated[AuthorCreate, Body(openapi_examples=AUTHOR_CREATE_EXAMPLES)],
    service: AuthorServiceTxDep,
) -> AuthorRead:
    return await service.create(payload)


@router.get('/{author_id}', response_model=AuthorRead, responses=READ_RESPONSES)
async def read_author(author_id: UUID, service: AuthorServiceDep) -> AuthorRead:
    return await service.get(author_id)


@router.patch('/{author_id}', response_model=AuthorRead, responses=UPDATE_RESPONSES)
async def update_author(
    author_id: UUID,
    payload: Annotated[AuthorUpdate, Body(openapi_examples=AUTHOR_UPDATE_EXAMPLES)],
    service: AuthorServiceTxDep,
) -> AuthorRead:
    return await service.update(author_id, payload)


@router.delete(
    '/{author_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=DELETE_RESPONSES,
)
async def delete_author(author_id: UUID, service: AuthorServiceTxDep) -> None:
    await service.delete(author_id)
