import logging
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.sql.base import ExecutableOption

from src.exceptions import NotFoundError
from src.infra.cache import CacheSession, build_key
from src.models.base import Base
from src.repository import Repo

logger = logging.getLogger(__name__)


class BaseService[RepoT: Repo, ModelT: Base, ReadT: BaseModel]:
    entity_name: str
    cache_namespace: str
    read_model: type[ReadT]
    load_options: tuple[ExecutableOption, ...] = ()

    def __init__(self, repo: RepoT, cache: CacheSession) -> None:
        self.repo = repo
        self.cache = cache

    def _cache_key(self, obj_id: UUID) -> str:
        return build_key(self.cache_namespace, obj_id)

    async def _get_or_raise(self, obj_id: UUID, *options: ExecutableOption) -> ModelT:
        obj: ModelT | None = await self.repo.get(obj_id, *options)
        if obj is None:
            logger.info('%s not found: %s', self.entity_name, obj_id)
            raise NotFoundError(f'{self.entity_name} {obj_id} not found')
        return obj

    async def get(self, obj_id: UUID) -> ReadT:
        key = self._cache_key(obj_id)
        cached = await self.cache.get(key)
        if cached is not None:
            try:
                return self.read_model.model_validate_json(cached)
            except ValidationError:
                logger.warning('unusable cached payload: %s', key, exc_info=True)
                await self.cache.delete(key)
        obj = await self._get_or_raise(obj_id, *self.load_options)
        read = self.read_model.model_validate(obj)
        await self.cache.add(key, read.model_dump_json().encode())
        return read
