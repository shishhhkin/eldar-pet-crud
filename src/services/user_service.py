import logging
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from src.exceptions import UserAlreadyExistsError, UserNotFoundError
from src.mappers.users import apply_user_update, to_user_profile_model, to_user_read
from src.models.users import UserModel
from src.repository import UserRepo
from src.schemas.users import UserCreate, UserRead, UserUpdate
from src.services.base import BaseService

logger = logging.getLogger(__name__)


class UserService(BaseService[UserRepo]):
    async def _get_or_raise(self, user_id: UUID, *options: ExecutableOption) -> UserModel:
        user = await self.repo.get(user_id, *options)
        if user is None:
            logger.info('user not found: %s', user_id)
            raise UserNotFoundError(user_id)
        return user

    async def create(self, payload: UserCreate) -> UserRead:
        await self.repo.advisory_lock('username', payload.username)
        await self.repo.advisory_lock('email', payload.email)
        user = await self.repo.create_ignoring_conflict(
            username=payload.username, email=payload.email
        )
        if user is None:
            logger.info('user already exists: %s', payload.username)
            raise UserAlreadyExistsError
        user.profile = to_user_profile_model(payload.profile)
        await self.repo.save(user, 'profile')
        return to_user_read(user)

    async def get(self, user_id: UUID) -> UserRead:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        return to_user_read(user)

    async def update(self, user_id: UUID, payload: UserUpdate) -> UserRead:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        if payload.username is not None:
            await self.repo.advisory_lock('username', payload.username)
            if await self.repo.exists(
                UserModel.username == payload.username, UserModel.id != user_id
            ):
                logger.info('user already exists: %s', payload.username)
                raise UserAlreadyExistsError
        if payload.email is not None:
            await self.repo.advisory_lock('email', payload.email)
            if await self.repo.exists(UserModel.email == payload.email, UserModel.id != user_id):
                logger.info('user already exists: %s', payload.email)
                raise UserAlreadyExistsError
        apply_user_update(user, payload)
        await self.repo.save(user)
        return to_user_read(user)

    async def delete(self, user_id: UUID) -> None:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        await self.repo.save(user)
