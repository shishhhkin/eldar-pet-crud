from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from src.db import SessionDep
from src.schemas.users import UserCreate, UserRead, UserUpdate
from src.services import user_service

router = APIRouter(prefix='/users', tags=['users'])


@router.post('', response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep) -> UserRead:
    async with session.begin():
        user = await user_service.create_user(session, payload)
    return UserRead.model_validate(user)


@router.get('/{user_id}', response_model=UserRead)
async def read_user(user_id: UUID, session: SessionDep) -> UserRead:
    user = await user_service.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return UserRead.model_validate(user)


@router.put('/{user_id}', response_model=UserRead)
async def update_user(user_id: UUID, payload: UserUpdate, session: SessionDep) -> UserRead:
    async with session.begin():
        user = await user_service.update_user(session, user_id, payload)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return UserRead.model_validate(user)


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, session: SessionDep) -> Response:
    async with session.begin():
        deleted = await user_service.delete_user(session, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)
