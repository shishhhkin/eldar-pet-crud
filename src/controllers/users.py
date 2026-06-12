from uuid import UUID

from fastapi import APIRouter, status

from src.dependencies import UserServiceDep, UserServiceTxDep
from src.schemas.users import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix='/users', tags=['users'])


@router.post('', response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, service: UserServiceTxDep) -> UserRead:
    return await service.create(payload)  # type: ignore[return-value]


@router.get('/{user_id}', response_model=UserRead)
async def read_user(user_id: UUID, service: UserServiceDep) -> UserRead:
    return await service.get(user_id)  # type: ignore[return-value]


@router.put('/{user_id}', response_model=UserRead)
async def update_user(user_id: UUID, payload: UserUpdate, service: UserServiceTxDep) -> UserRead:
    return await service.update(user_id, payload)  # type: ignore[return-value]


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, service: UserServiceTxDep) -> None:
    await service.delete(user_id)
