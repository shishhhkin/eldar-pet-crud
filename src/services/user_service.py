import logging
from uuid import UUID

from src.clients.library import LibraryClient
from src.exceptions import (
    AlreadyExistsError,
    ExternalServiceBadResponseError,
    ExternalServiceUnavailableError,
)
from src.infra.cache import Cache
from src.infra.db import UnitOfWork
from src.mappers.users import apply_user_update, to_user_profile_model, to_user_read
from src.models.users import UserModel
from src.repository import CacheInvalidationRepo, PendingMembershipRepo, UserRepo
from src.schemas.users import UserCreate, UserRead, UserUpdate
from src.services.base import BaseService, Cacheable
from src.services.membership_service import MembershipService

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
        membership_service: MembershipService,
        pending_memberships: PendingMembershipRepo,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(repo, invalidations, cache)
        self.library = library
        self.membership_service = membership_service
        self.pending_memberships = pending_memberships
        self.uow = uow

    async def create(self, payload: UserCreate) -> UserRead:
        async with self.uow:
            user = await self._create(payload)
            await self.pending_memberships.add(user.id, self.membership_service.lease)
        membership = await self.membership_service.issue(user.id)
        return to_user_read(user, membership)

    async def _create(self, payload: UserCreate) -> UserModel:
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
        return user

    async def _read(self, obj: UserModel) -> tuple[UserRead, Cacheable]:
        if obj.membership is None:
            return self.read_model.model_validate(obj), False
        membership_id = obj.membership.id
        await self.uow.release_connection()
        try:
            membership = await self.library.get_membership(membership_id)
        except ExternalServiceUnavailableError as exc:
            logger.warning('membership not fetched: user_id=%s (%s)', obj.id, exc)
            raise
        except ExternalServiceBadResponseError as exc:
            logger.error(
                'membership not fetched: user_id=%s membership_id=%s (%s)',
                obj.id,
                membership_id,
                exc,
            )
            raise
        return to_user_read(obj, await self.membership_service.store(membership)), True

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
        await self.pending_memberships.cancel(user_id)
        user = await self._get_or_raise(user_id)
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        if user.membership is not None:
            user.membership.is_deleted = True
        await self.repo.save(user)
        await self._invalidate(user_id)
