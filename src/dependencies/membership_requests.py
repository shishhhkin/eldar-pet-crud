from typing import Annotated

from fastapi import Depends

from src.dependencies.db import SessionDep, TxSessionDep
from src.repository import MembershipRequestRepo


def _membership_request_repo(session: SessionDep) -> MembershipRequestRepo:
    return MembershipRequestRepo(session)


def _membership_request_repo_tx(session: TxSessionDep) -> MembershipRequestRepo:
    return MembershipRequestRepo(session)


MembershipRequestRepoDep = Annotated[MembershipRequestRepo, Depends(_membership_request_repo)]
MembershipRequestRepoTxDep = Annotated[MembershipRequestRepo, Depends(_membership_request_repo_tx)]
