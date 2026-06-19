from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.user_profiles import UserProfileModel
from src.models.users import UserModel
from src.repository import Repo
from src.schemas.users import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = Repo(session, UserModel)

    async def create(self, payload: UserCreate) -> UserModel:
        user = UserModel(
            **payload.model_dump(mode='json', exclude={'profile'}),
            profile=UserProfileModel(**payload.profile.model_dump(mode='json')),
        )
        self.repo.add(user)
        await self.repo.flush()
        await self.repo.refresh(user, ['profile'])
        return user

    async def get(self, user_id: UUID) -> UserModel:
        return await self.repo.get(user_id, selectinload(UserModel.profile))

    async def update(self, user_id: UUID, payload: UserUpdate) -> UserModel:
        user = await self.repo.get(user_id, selectinload(UserModel.profile))

        if payload.username is not None:
            user.username = payload.username
        if payload.email is not None:
            user.email = payload.email

        if payload.profile is not None:
            profile_data = payload.profile.model_dump(mode='json')
            if user.profile is None:
                user.profile = UserProfileModel(**profile_data)
            else:
                for key, value in profile_data.items():
                    setattr(user.profile, key, value)

        await self.repo.flush()
        return user

    async def delete(self, user_id: UUID) -> None:
        user = await self.repo.get(user_id, selectinload(UserModel.profile))
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        await self.repo.flush()
