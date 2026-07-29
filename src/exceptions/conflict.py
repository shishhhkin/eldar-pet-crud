from http import HTTPStatus

from src.exceptions.base import AppError


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = 'conflict'


class AlreadyExistsError(ConflictError):
    code = 'already_exists'
    entity = 'Object'
    message_template = '{entity} already exists'

    def __init__(self) -> None:
        super().__init__(self.message_template.format(entity=self.entity))


class GenreAlreadyExistsError(AlreadyExistsError):
    entity = 'Genre'


class UserAlreadyExistsError(AlreadyExistsError):
    entity = 'User'
