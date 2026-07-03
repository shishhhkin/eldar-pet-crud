import logging
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from src.exceptions import UserNotFoundError
from src.mappers.users import apply_user_update, to_user_model, to_user_read
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
        user = to_user_model(payload)
        await self.repo.save(user, 'profile')
        return to_user_read(user)

    async def get(self, user_id: UUID) -> UserRead:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        return to_user_read(user)

    async def update(self, user_id: UUID, payload: UserUpdate) -> UserRead:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        apply_user_update(user, payload)
        await self.repo.save(user)
        return to_user_read(user)

    async def delete(self, user_id: UUID) -> None:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        await self.repo.save(user)
