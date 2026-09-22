from typing import Annotated

from fastapi import Depends

from src.dependencies.cache import CacheDep
from src.dependencies.db import SessionDep, TxSessionDep
from src.repository import AuthorRepo
from src.services.author_service import AuthorService


def _author_repo(session: SessionDep) -> AuthorRepo:
    return AuthorRepo(session)


def _author_repo_tx(session: TxSessionDep) -> AuthorRepo:
    return AuthorRepo(session)


AuthorRepoDep = Annotated[AuthorRepo, Depends(_author_repo)]
AuthorRepoTxDep = Annotated[AuthorRepo, Depends(_author_repo_tx)]


def _author_service(repo: AuthorRepoDep, cache: CacheDep) -> AuthorService:
    return AuthorService(repo, cache)


def _author_service_tx(repo: AuthorRepoTxDep, cache: CacheDep) -> AuthorService:
    return AuthorService(repo, cache)


AuthorServiceDep = Annotated[AuthorService, Depends(_author_service)]
AuthorServiceTxDep = Annotated[AuthorService, Depends(_author_service_tx)]
