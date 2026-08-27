from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.cache import Cache, cache
from src.db import SessionFactory, readonly_session, tx_session
from src.repository import AuthorRepo, GenreRepo, UserRepo
from src.repository.base import pop_invalidation_keys
from src.services.author_service import AuthorService
from src.services.genre_service import GenreService
from src.services.user_service import UserService


def get_cache() -> Cache:
    return cache


CacheDep = Annotated[Cache, Depends(get_cache)]


async def get_session() -> AsyncIterator[AsyncSession]:
    async with readonly_session(SessionFactory) as session:
        yield session


@asynccontextmanager
async def invalidating_tx_session(
    session_factory: async_sessionmaker[AsyncSession],
    cache: Cache,
) -> AsyncGenerator[AsyncSession]:
    async with tx_session(session_factory) as session:
        yield session
    for key in pop_invalidation_keys(session):
        await cache.delete(key)


async def get_tx_session(cache: CacheDep) -> AsyncIterator[AsyncSession]:
    async with invalidating_tx_session(SessionFactory, cache) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
TxSessionDep = Annotated[AsyncSession, Depends(get_tx_session)]


def _author_repo(session: SessionDep) -> AuthorRepo:
    return AuthorRepo(session)


def _author_repo_tx(session: TxSessionDep) -> AuthorRepo:
    return AuthorRepo(session)


def _genre_repo(session: SessionDep) -> GenreRepo:
    return GenreRepo(session)


def _genre_repo_tx(session: TxSessionDep) -> GenreRepo:
    return GenreRepo(session)


def _user_repo(session: SessionDep) -> UserRepo:
    return UserRepo(session)


def _user_repo_tx(session: TxSessionDep) -> UserRepo:
    return UserRepo(session)


AuthorRepoDep = Annotated[AuthorRepo, Depends(_author_repo)]
AuthorRepoTxDep = Annotated[AuthorRepo, Depends(_author_repo_tx)]
GenreRepoDep = Annotated[GenreRepo, Depends(_genre_repo)]
GenreRepoTxDep = Annotated[GenreRepo, Depends(_genre_repo_tx)]
UserRepoDep = Annotated[UserRepo, Depends(_user_repo)]
UserRepoTxDep = Annotated[UserRepo, Depends(_user_repo_tx)]


def _author_service(repo: AuthorRepoDep, cache: CacheDep) -> AuthorService:
    return AuthorService(repo, cache)


def _author_service_tx(repo: AuthorRepoTxDep, cache: CacheDep) -> AuthorService:
    return AuthorService(repo, cache)


def _genre_service(repo: GenreRepoDep, cache: CacheDep) -> GenreService:
    return GenreService(repo, cache)


def _genre_service_tx(repo: GenreRepoTxDep, cache: CacheDep) -> GenreService:
    return GenreService(repo, cache)


def _user_service(repo: UserRepoDep, cache: CacheDep) -> UserService:
    return UserService(repo, cache)


def _user_service_tx(repo: UserRepoTxDep, cache: CacheDep) -> UserService:
    return UserService(repo, cache)


AuthorServiceDep = Annotated[AuthorService, Depends(_author_service)]
AuthorServiceTxDep = Annotated[AuthorService, Depends(_author_service_tx)]

GenreServiceDep = Annotated[GenreService, Depends(_genre_service)]
GenreServiceTxDep = Annotated[GenreService, Depends(_genre_service_tx)]

UserServiceDep = Annotated[UserService, Depends(_user_service)]
UserServiceTxDep = Annotated[UserService, Depends(_user_service_tx)]
