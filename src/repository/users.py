from sqlalchemy.ext.asyncio import AsyncSession

from src.models.users import UserModel
from src.repository.base import Repo


class UserRepo(Repo[UserModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel)

    async def create_ignoring_conflict(self, *, username: str, email: str) -> UserModel | None:
        user = await self.insert_ignoring_conflict(username=username, email=email)
        if user is not None:
            await self.session.refresh(user, attribute_names=['profile'])
        return user
