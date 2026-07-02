from src.exceptions.base import AppError
from src.exceptions.not_found import (
    AuthorNotFoundError,
    GenreNotFoundError,
    NotFoundError,
    ObjectNotFoundError,
    UserNotFoundError,
)

__all__ = [
    'AppError',
    'AuthorNotFoundError',
    'GenreNotFoundError',
    'NotFoundError',
    'ObjectNotFoundError',
    'UserNotFoundError',
]
