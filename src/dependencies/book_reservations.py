from typing import Annotated

from fastapi import Depends

from src.dependencies.book_reservation_outbox import BookReservationOutboxRepoTxDep
from src.dependencies.db import TxSessionDep
from src.repository import BookReservationRepo
from src.services.book_reservation_service import BookReservationService


def _book_reservation_repo_tx(session: TxSessionDep) -> BookReservationRepo:
    return BookReservationRepo(session)


BookReservationRepoTxDep = Annotated[BookReservationRepo, Depends(_book_reservation_repo_tx)]


def _book_reservation_service_tx(
    repo: BookReservationRepoTxDep, outbox: BookReservationOutboxRepoTxDep
) -> BookReservationService:
    return BookReservationService(repo, outbox)


BookReservationServiceTxDep = Annotated[
    BookReservationService, Depends(_book_reservation_service_tx)
]
