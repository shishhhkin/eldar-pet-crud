from http import HTTPStatus
from uuid import UUID


class AppError(Exception):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    code = 'internal_error'

    def __init__(self, message: str = 'Internal server error') -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = 'not_found'


class ValidationAppError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = 'validation_error'


class ObjectNotFoundError(NotFoundError):
    def __init__(self, model: type, object_id: UUID) -> None:
        super().__init__(f'{model.__name__} {object_id} not found')
