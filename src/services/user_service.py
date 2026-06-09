from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import ObjectNotFoundError
from src.models.user_profiles import UserProfileModel
from src.models.users import UserModel
from src.schemas.users import UserCreate, UserUpdate


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
        await self.session.flush()
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

        await self.session.flush()
        return user

    async def delete(self, user_id: UUID) -> None:
        user = await self._get_with_profile(user_id)
        user.is_deleted = True
        if user.profile is not None:
            user.profile.is_deleted = True
        await self.session.flush()
