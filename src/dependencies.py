from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session, get_tx_session
from src.repository import AuthorRepo, GenreRepo, UserRepo
from src.services.author_service import AuthorService
from src.services.genre_service import GenreService
from src.services.user_service import UserService

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


def _author_service(repo: AuthorRepoDep) -> AuthorService:
    return AuthorService(repo)


def _author_service_tx(repo: AuthorRepoTxDep) -> AuthorService:
    return AuthorService(repo)


def _genre_service(repo: GenreRepoDep) -> GenreService:
    return GenreService(repo)


def _genre_service_tx(repo: GenreRepoTxDep) -> GenreService:
    return GenreService(repo)


def _user_service(repo: UserRepoDep) -> UserService:
    return UserService(repo)


def _user_service_tx(repo: UserRepoTxDep) -> UserService:
    return UserService(repo)


AuthorServiceDep = Annotated[AuthorService, Depends(_author_service)]
AuthorServiceTxDep = Annotated[AuthorService, Depends(_author_service_tx)]

GenreServiceDep = Annotated[GenreService, Depends(_genre_service)]
GenreServiceTxDep = Annotated[GenreService, Depends(_genre_service_tx)]

UserServiceDep = Annotated[UserService, Depends(_user_service)]
UserServiceTxDep = Annotated[UserService, Depends(_user_service_tx)]
