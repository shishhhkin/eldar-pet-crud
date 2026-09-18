import logging
from uuid import UUID

from src.exceptions import AlreadyExistsError
from src.mappers.users import apply_user_update, to_user_profile_model
from src.models.users import UserModel
from src.repository import UserRepo
from src.schemas.users import UserCreate, UserRead, UserUpdate
from src.services.base import BaseService

logger = logging.getLogger(__name__)


class UserService(BaseService[UserRepo, UserModel, UserRead]):
    entity_name = 'User'
    cache_namespace = 'user'
    read_model = UserRead

    async def create(self, payload: UserCreate) -> UserRead:
        await self.repo.advisory_lock('username', payload.username)
        await self.repo.advisory_lock('email', payload.email)
        user = await self.repo.create_ignoring_conflict(
            username=payload.username, email=payload.email
        )
        if user is None:
            logger.info(
                'user already exists: username=%s email=%s', payload.username, payload.email
            )
            raise AlreadyExistsError('User with this username or email already exists')
        user.profile = to_user_profile_model(payload.profile)
        await self.repo.save(user, 'profile')
        return self.read_model.model_validate(user)

    async def update(self, user_id: UUID, payload: UserUpdate) -> UserRead:
        user = await self._get_or_raise(user_id)
        if payload.username is not None:
            await self.repo.advisory_lock('username', payload.username)
            if await self.repo.exists(
                UserModel.username == payload.username, UserModel.id != user_id
            ):
                logger.info('username already exists: %s', payload.username)
                raise AlreadyExistsError('User with this username already exists')
        if payload.email is not None:
            await self.repo.advisory_lock('email', payload.email)
            if await self.repo.exists(UserModel.email == payload.email, UserModel.id != user_id):
                logger.info('email already exists: %s', payload.email)
                raise AlreadyExistsError('User with this email already exists')
        apply_user_update(user, payload)
        await self.repo.save(user)
        await self._invalidate(user_id)
        return self.read_model.model_validate(user)

    async def delete(self, user_id: UUID) -> None:
        user = await self._get_or_raise(user_id)
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        await self.repo.save(user)
        await self._invalidate(user_id)
