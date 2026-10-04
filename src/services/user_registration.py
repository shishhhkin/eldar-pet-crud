import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.exceptions import AlreadyExistsError
from src.infra.db import tx_session
from src.mappers.users import to_user_profile_model, to_user_read
from src.models.users import UserModel
from src.repository import UserRepo
from src.schemas.users import UserCreate, UserRead
from src.services.membership_issuer import MembershipIssuer

logger = logging.getLogger(__name__)


class UserRegistration:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo_factory: Callable[[AsyncSession], UserRepo],
        issuer: MembershipIssuer,
    ) -> None:
        self.session_factory = session_factory
        self.repo_factory = repo_factory
        self.issuer = issuer

    async def register(self, payload: UserCreate) -> UserRead:
        async with tx_session(self.session_factory) as session:
            user = await self._create(self.repo_factory(session), payload)
        membership = await self.issuer.issue(user.id)
        return to_user_read(user, membership)

    async def _create(self, repo: UserRepo, payload: UserCreate) -> UserModel:
        await repo.advisory_lock('username', payload.username)
        await repo.advisory_lock('email', payload.email)
        user = await repo.create_ignoring_conflict(username=payload.username, email=payload.email)
        if user is None:
            logger.info(
                'user already exists: username=%s email=%s', payload.username, payload.email
            )
            raise AlreadyExistsError('User with this username or email already exists')
        user.profile = to_user_profile_model(payload.profile)
        await repo.save(user, 'profile')
        return user
