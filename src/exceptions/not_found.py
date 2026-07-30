from http import HTTPStatus

from src.exceptions.base import AppError


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = 'not_found'
    default_message = 'Not found'
