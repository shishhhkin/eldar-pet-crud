from typing import Annotated

from fastapi import Depends

from src.dependencies.cache import CacheDep
from src.dependencies.db import SessionDep, TxSessionDep
from src.repository import UserRepo
from src.services.user_service import UserService


def _user_repo(session: SessionDep) -> UserRepo:
    return UserRepo(session)


def _user_repo_tx(session: TxSessionDep) -> UserRepo:
    return UserRepo(session)


UserRepoDep = Annotated[UserRepo, Depends(_user_repo)]
UserRepoTxDep = Annotated[UserRepo, Depends(_user_repo_tx)]


def _user_service(repo: UserRepoDep, cache: CacheDep) -> UserService:
    return UserService(repo, cache)


def _user_service_tx(repo: UserRepoTxDep, cache: CacheDep) -> UserService:
    return UserService(repo, cache)


UserServiceDep = Annotated[UserService, Depends(_user_service)]
UserServiceTxDep = Annotated[UserService, Depends(_user_service_tx)]
