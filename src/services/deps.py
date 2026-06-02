from typing import Annotated

from fastapi import Depends

from src.db import SessionDep, TxSessionDep
from src.services.author_service import AuthorService
from src.services.book_service import BookService
from src.services.genre_service import GenreService
from src.services.user_service import UserService


def _author_service(session: SessionDep) -> AuthorService:
    return AuthorService(session)


def _author_service_tx(session: TxSessionDep) -> AuthorService:
    return AuthorService(session)


def _book_service(session: SessionDep) -> BookService:
    return BookService(session)


def _book_service_tx(session: TxSessionDep) -> BookService:
    return BookService(session)


def _genre_service(session: SessionDep) -> GenreService:
    return GenreService(session)


def _genre_service_tx(session: TxSessionDep) -> GenreService:
    return GenreService(session)


def _user_service(session: SessionDep) -> UserService:
    return UserService(session)


def _user_service_tx(session: TxSessionDep) -> UserService:
    return UserService(session)


AuthorServiceDep = Annotated[AuthorService, Depends(_author_service)]
AuthorServiceTxDep = Annotated[AuthorService, Depends(_author_service_tx)]

BookServiceDep = Annotated[BookService, Depends(_book_service)]
BookServiceTxDep = Annotated[BookService, Depends(_book_service_tx)]

GenreServiceDep = Annotated[GenreService, Depends(_genre_service)]
GenreServiceTxDep = Annotated[GenreService, Depends(_genre_service_tx)]

UserServiceDep = Annotated[UserService, Depends(_user_service)]
UserServiceTxDep = Annotated[UserService, Depends(_user_service_tx)]
