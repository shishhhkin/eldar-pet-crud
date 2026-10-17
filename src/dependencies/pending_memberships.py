from typing import Annotated

from fastapi import Depends

from src.dependencies.db import SessionDep, TxSessionDep
from src.repository import PendingMembershipRepo


def _pending_membership_repo(session: SessionDep) -> PendingMembershipRepo:
    return PendingMembershipRepo(session)


def _pending_membership_repo_tx(session: TxSessionDep) -> PendingMembershipRepo:
    return PendingMembershipRepo(session)


PendingMembershipRepoDep = Annotated[PendingMembershipRepo, Depends(_pending_membership_repo)]
PendingMembershipRepoTxDep = Annotated[PendingMembershipRepo, Depends(_pending_membership_repo_tx)]
