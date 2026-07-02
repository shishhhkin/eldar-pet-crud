from http import HTTPStatus

from src.exceptions.base import AppError


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = 'conflict'


class AlreadyExistsError(ConflictError):
    code = 'already_exists'

    def __init__(self, entity: str) -> None:
        super().__init__(f'{entity} already exists')
