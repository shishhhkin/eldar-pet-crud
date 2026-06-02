import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import SessionDep, TxSessionDep
from src.exceptions import ConstraintViolationError, ObjectNotFoundError
from src.models.user_profiles import UserProfileModel
from src.models.users import UserModel
from src.schemas.users import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_with_profile(self, user_id: UUID) -> UserModel:
        stmt = (
            select(UserModel)
            .where(UserModel.id == user_id)
            .options(selectinload(UserModel.profile))
        )
        user = (await self.session.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise ObjectNotFoundError(UserModel, user_id)
        return user

    async def create(self, payload: UserCreate) -> UserModel:
        user = UserModel(
            **payload.model_dump(mode='json', exclude={'profile'}),
            profile=UserProfileModel(**payload.profile.model_dump(mode='json')),
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error creating user: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(f'failed to create user: {str(e.orig)}') from e
        await self.session.refresh(user, attribute_names=['profile'])
        return user

    async def get(self, user_id: UUID) -> UserModel:
        return await self._get_with_profile(user_id)

    async def update(self, user_id: UUID, payload: UserUpdate) -> UserModel:
        user = await self._get_with_profile(user_id)

        for field, value in payload.model_dump(mode='json', exclude={'profile'}).items():
            setattr(user, field, value)

        profile_data = payload.profile.model_dump(mode='json')
        if user.profile is None:
            user.profile = UserProfileModel(**profile_data)
        else:
            for key, value in profile_data.items():
                setattr(user.profile, key, value)

        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error updating user {user_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to update user {user_id}: {str(e.orig)}'
            ) from e
        return user

    async def delete(self, user_id: UUID) -> None:
        user = await self._get_with_profile(user_id)
        await self.session.delete(user)
        try:
            await self.session.flush()
        except IntegrityError as e:
            msg = f'integrity error deleting user {user_id}: {e.orig}'
            logger.error(msg, exc_info=True)
            raise ConstraintViolationError(
                f'failed to delete user {user_id}: {str(e.orig)}'
            ) from e


def _user_service(session: SessionDep) -> UserService:
    return UserService(session)


def _user_service_tx(session: TxSessionDep) -> UserService:
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(_user_service)]
UserServiceTxDep = Annotated[UserService, Depends(_user_service_tx)]
