from typing import Annotated

from fastapi import Depends

from src.dependencies.db import TxSessionDep
from src.repository import BookReservationOutboxRepo


def _book_reservation_outbox_repo_tx(session: TxSessionDep) -> BookReservationOutboxRepo:
    return BookReservationOutboxRepo(session)


BookReservationOutboxRepoTxDep = Annotated[
    BookReservationOutboxRepo, Depends(_book_reservation_outbox_repo_tx)
]
