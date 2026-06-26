from sqlalchemy.ext.asyncio import AsyncSession

from src.models.users import UserModel
from src.repository.base import Repo


class UserRepo(Repo[UserModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel)
