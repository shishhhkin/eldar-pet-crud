from typing import Annotated

from fastapi import Depends

from src.dependencies.cache import CacheDep
from src.dependencies.db import SessionDep, TxSessionDep
from src.repository import GenreRepo
from src.services.genre_service import GenreService


def _genre_repo(session: SessionDep) -> GenreRepo:
    return GenreRepo(session)


def _genre_repo_tx(session: TxSessionDep) -> GenreRepo:
    return GenreRepo(session)


GenreRepoDep = Annotated[GenreRepo, Depends(_genre_repo)]
GenreRepoTxDep = Annotated[GenreRepo, Depends(_genre_repo_tx)]


def _genre_service(repo: GenreRepoDep, cache: CacheDep) -> GenreService:
    return GenreService(repo, cache)


def _genre_service_tx(repo: GenreRepoTxDep, cache: CacheDep) -> GenreService:
    return GenreService(repo, cache)


GenreServiceDep = Annotated[GenreService, Depends(_genre_service)]
GenreServiceTxDep = Annotated[GenreService, Depends(_genre_service_tx)]
