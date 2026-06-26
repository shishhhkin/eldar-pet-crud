from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.mappers.users import apply_user_update, to_user_model, to_user_read
from src.models.users import UserModel
from src.repository import UserRepo
from src.schemas.users import UserCreate, UserRead, UserUpdate
from src.services.base import BaseService


class UserService(BaseService[UserModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = UserRepo(session)

    async def create(self, payload: UserCreate) -> UserRead:
        user = to_user_model(payload)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user, attribute_names=['profile'])
        return to_user_read(user)

    async def get(self, user_id: UUID) -> UserRead:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        return to_user_read(user)

    async def update(self, user_id: UUID, payload: UserUpdate) -> UserRead:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        apply_user_update(user, payload)
        await self.session.flush()
        return to_user_read(user)

    async def delete(self, user_id: UUID) -> None:
        user = await self._get_or_raise(user_id, selectinload(UserModel.profile))
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        await self.session.flush()
