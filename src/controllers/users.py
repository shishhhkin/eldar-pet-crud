from uuid import UUID

from fastapi import APIRouter, status

from src.db import SessionDep, TxSessionDep
from src.schemas.users import UserCreate, UserRead, UserUpdate
from src.services import user_service

router = APIRouter(prefix='/users', tags=['users'])


@router.post('', response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: TxSessionDep) -> UserRead:
    return await user_service.create_user(session, payload)  # type: ignore[return-value]


@router.get('/{user_id}', response_model=UserRead)
async def read_user(user_id: UUID, session: SessionDep) -> UserRead:
    return await user_service.get_user(session, user_id)  # type: ignore[return-value]


@router.put('/{user_id}', response_model=UserRead)
async def update_user(user_id: UUID, payload: UserUpdate, session: TxSessionDep) -> UserRead:
    return await user_service.update_user(session, user_id, payload)  # type: ignore[return-value]


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, session: TxSessionDep) -> None:
    await user_service.delete_user(session, user_id)
