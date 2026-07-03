from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from src.dependencies import UserServiceDep, UserServiceTxDep
from src.schemas.errors import (
    CREATE_RESPONSES,
    DELETE_RESPONSES,
    READ_RESPONSES,
    UPDATE_RESPONSES,
)
from src.schemas.examples import USER_CREATE_EXAMPLES, USER_UPDATE_EXAMPLES
from src.schemas.users import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix='/users', tags=['users'])


@router.post(
    '',
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses=CREATE_RESPONSES,
)
async def create_user(
    payload: Annotated[UserCreate, Body(openapi_examples=USER_CREATE_EXAMPLES)],
    service: UserServiceTxDep,
) -> UserRead:
    return await service.create(payload)


@router.get('/{user_id}', response_model=UserRead, responses=READ_RESPONSES)
async def read_user(user_id: UUID, service: UserServiceDep) -> UserRead:
    return await service.get(user_id)


@router.patch('/{user_id}', response_model=UserRead, responses=UPDATE_RESPONSES)
async def update_user(
    user_id: UUID,
    payload: Annotated[UserUpdate, Body(openapi_examples=USER_UPDATE_EXAMPLES)],
    service: UserServiceTxDep,
) -> UserRead:
    return await service.update(user_id, payload)


@router.delete(
    '/{user_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=DELETE_RESPONSES,
)
async def delete_user(user_id: UUID, service: UserServiceTxDep) -> None:
    await service.delete(user_id)
