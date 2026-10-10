from typing import Annotated

from fastapi import Depends

from src.dependencies.cache import CacheDep
from src.dependencies.cache_invalidations import (
    CacheInvalidationRepoDep,
    CacheInvalidationRepoTxDep,
)
from src.dependencies.db import SessionDep, TxSessionDep
from src.dependencies.library import LibraryClientDep
from src.dependencies.membership_issuer import MembershipIssuerDep
from src.dependencies.membership_requests import (
    MembershipRequestRepoDep,
    MembershipRequestRepoTxDep,
)
from src.infra.uow import UnitOfWork
from src.repository import UserRepo
from src.services.user_service import UserService


def _user_repo(session: SessionDep) -> UserRepo:
    return UserRepo(session)


def _user_repo_tx(session: TxSessionDep) -> UserRepo:
    return UserRepo(session)


UserRepoDep = Annotated[UserRepo, Depends(_user_repo)]
UserRepoTxDep = Annotated[UserRepo, Depends(_user_repo_tx)]


def _user_service(
    repo: UserRepoDep,
    invalidations: CacheInvalidationRepoDep,
    cache: CacheDep,
    library: LibraryClientDep,
    issuer: MembershipIssuerDep,
    requests: MembershipRequestRepoDep,
    session: SessionDep,
) -> UserService:
    return UserService(repo, invalidations, cache, library, issuer, requests, UnitOfWork(session))


def _user_service_tx(
    repo: UserRepoTxDep,
    invalidations: CacheInvalidationRepoTxDep,
    cache: CacheDep,
    library: LibraryClientDep,
    issuer: MembershipIssuerDep,
    requests: MembershipRequestRepoTxDep,
    session: TxSessionDep,
) -> UserService:
    return UserService(repo, invalidations, cache, library, issuer, requests, UnitOfWork(session))


UserServiceDep = Annotated[UserService, Depends(_user_service)]
UserServiceTxDep = Annotated[UserService, Depends(_user_service_tx)]
