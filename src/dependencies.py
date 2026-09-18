from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infra.cache import Cache
from src.infra.db import readonly_session
from src.infra.invalidation import InvalidationOutbox
from src.infra.unit_of_work import invalidating_tx_session
from src.repository import AuthorRepo, GenreRepo, UserRepo
from src.services.author_service import AuthorService
from src.services.genre_service import GenreService
from src.services.user_service import UserService


def get_cache(request: Request) -> Cache:
    return cast('Cache', request.app.state.cache)


def get_outbox(request: Request) -> InvalidationOutbox:
    return cast('InvalidationOutbox', request.app.state.outbox)


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast('async_sessionmaker[AsyncSession]', request.app.state.session_factory)


CacheDep = Annotated[Cache, Depends(get_cache)]
OutboxDep = Annotated[InvalidationOutbox, Depends(get_outbox)]
SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


async def get_session(session_factory: SessionFactoryDep) -> AsyncIterator[AsyncSession]:
    async with readonly_session(session_factory) as session:
        yield session


async def get_tx_session(
    session_factory: SessionFactoryDep,
    outbox: OutboxDep,
) -> AsyncIterator[AsyncSession]:
    async with invalidating_tx_session(session_factory, outbox) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
TxSessionDep = Annotated[AsyncSession, Depends(get_tx_session, scope='function')]


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
