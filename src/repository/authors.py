from sqlalchemy.ext.asyncio import AsyncSession

from src.models.authors import AuthorModel
from src.repository.base import Repo


class AuthorRepo(Repo[AuthorModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuthorModel)
