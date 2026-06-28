from typing import cast
from uuid import UUID

from sqlalchemy.sql.base import ExecutableOption

from src.exceptions import ObjectNotFoundError
from src.models.base import Base
from src.repository import Repo


class BaseService[ModelT: Base, RepoT: Repo]:
    not_found_error: type[ObjectNotFoundError]

    def __init__(self, repo: RepoT) -> None:
        self.repo = repo

    async def _get_or_raise(self, obj_id: UUID, *options: ExecutableOption) -> ModelT:
        obj = await self.repo.get(obj_id, *options)
        if obj is None:
            raise self.not_found_error(obj_id)
        return cast('ModelT', obj)
