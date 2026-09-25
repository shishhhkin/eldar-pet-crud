from typing import Annotated

from fastapi import Depends

from src.dependencies.db import SessionDep, TxSessionDep
from src.repository import CacheInvalidationRepo


def _cache_invalidation_repo(session: SessionDep) -> CacheInvalidationRepo:
    return CacheInvalidationRepo(session)


def _cache_invalidation_repo_tx(session: TxSessionDep) -> CacheInvalidationRepo:
    return CacheInvalidationRepo(session)


CacheInvalidationRepoDep = Annotated[CacheInvalidationRepo, Depends(_cache_invalidation_repo)]
CacheInvalidationRepoTxDep = Annotated[CacheInvalidationRepo, Depends(_cache_invalidation_repo_tx)]
