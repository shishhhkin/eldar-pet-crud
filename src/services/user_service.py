from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.mappers.users import apply_user_update, to_user_model
from src.models.users import UserModel
from src.repository import Repo
from src.schemas.users import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = Repo(session, UserModel)

    async def create(self, payload: UserCreate) -> UserModel:
        user = to_user_model(payload)
        self.repo.add(user)
        await self.repo.flush()
        await self.repo.refresh(user, ['profile'])
        return user

    async def get(self, user_id: UUID) -> UserModel:
        return await self.repo.get(user_id, selectinload(UserModel.profile))

    async def update(self, user_id: UUID, payload: UserUpdate) -> UserModel:
        user = await self.repo.get(user_id, selectinload(UserModel.profile))
        apply_user_update(user, payload)
        await self.repo.flush()
        return user

    async def delete(self, user_id: UUID) -> None:
        user = await self.repo.get(user_id, selectinload(UserModel.profile))
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        await self.repo.flush()
