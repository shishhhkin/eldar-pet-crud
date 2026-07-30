from http import HTTPStatus

from src.exceptions.base import AppError


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = 'conflict'
    default_message = 'Conflict'


class AlreadyExistsError(ConflictError):
    code = 'already_exists'
    default_message = 'Already exists'
