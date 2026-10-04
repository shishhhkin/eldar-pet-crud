import logging
from uuid import UUID

from src.exceptions import AlreadyExistsError, LibraryUnavailableError
from src.infra.cache import Cache
from src.infra.library import LibraryClient
from src.mappers.users import apply_user_update, to_user_read
from src.models.users import UserModel
from src.repository import CacheInvalidationRepo, UserRepo
from src.schemas.users import UserRead, UserUpdate
from src.services.base import BaseService, Cacheable
from src.services.membership_issuer import MembershipIssuer

logger = logging.getLogger(__name__)


class UserService(BaseService[UserRepo, UserModel, UserRead]):
    entity_name = 'User'
    cache_namespace = 'user'
    read_model = UserRead

    def __init__(
        self,
        repo: UserRepo,
        invalidations: CacheInvalidationRepo,
        cache: Cache,
        library: LibraryClient,
        issuer: MembershipIssuer,
    ) -> None:
        super().__init__(repo, invalidations, cache)
        self.library = library
        self.issuer = issuer

    async def _read(self, obj: UserModel) -> tuple[UserRead, Cacheable]:
        local = self.read_model.model_validate(obj)
        if obj.membership is None:
            return local, False
        membership_id = obj.membership.id
        await self.repo.release()
        try:
            membership = await self.library.get_membership(membership_id)
        except LibraryUnavailableError as exc:
            logger.warning('serving membership copy: user_id=%s (%s)', obj.id, exc)
            return local, False
        if membership is None:
            logger.error(
                'membership missing in library: user_id=%s membership_id=%s',
                obj.id,
                membership_id,
            )
            return to_user_read(obj, None), False
        return to_user_read(obj, await self.issuer.store(membership)), True

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
        if user.membership is not None:
            user.membership.is_deleted = True
        await self.repo.save(user)
        await self._invalidate(user_id)
