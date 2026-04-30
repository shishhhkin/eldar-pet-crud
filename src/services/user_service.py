from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import UserNotFound
from src.models.user_profiles import UserProfileModel
from src.models.users import UserModel
from src.schemas.users import UserCreate, UserUpdate


async def _get_with_profile(session: AsyncSession, user_id: UUID) -> UserModel | None:
    stmt = select(UserModel).where(UserModel.id == user_id).options(selectinload(UserModel.profile))
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_user(session: AsyncSession, payload: UserCreate) -> UserModel:
    user = UserModel(
        username=payload.username,
        email=payload.email,
        profile=UserProfileModel(
            avatar_url=payload.profile.avatar_url,
            bio=payload.profile.bio,
            socials=payload.profile.socials,
        ),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user, attribute_names=['profile'])
    return user


async def get_user(session: AsyncSession, user_id: UUID) -> UserModel:
    user = await _get_with_profile(session, user_id)
    if user is None:
        raise UserNotFound(user_id)
    return user


async def update_user(
    session: AsyncSession, user_id: UUID, payload: UserUpdate
) -> UserModel:
    user = await _get_with_profile(session, user_id)
    if user is None:
        raise UserNotFound(user_id)

    user.username = payload.username
    user.email = payload.email

    if user.profile is None:
        user.profile = UserProfileModel(
            avatar_url=payload.profile.avatar_url,
            bio=payload.profile.bio,
            socials=payload.profile.socials,
        )
    else:
        user.profile.avatar_url = payload.profile.avatar_url
        user.profile.bio = payload.profile.bio
        user.profile.socials = payload.profile.socials

    await session.flush()
    return user


async def delete_user(session: AsyncSession, user_id: UUID) -> None:
    user = await session.get(UserModel, user_id)
    if user is None:
        raise UserNotFound(user_id)
    await session.delete(user)
    await session.flush()
