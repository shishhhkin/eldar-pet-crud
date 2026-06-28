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


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = 'conflict'


class ObjectNotFoundError(NotFoundError):
    entity = 'Object'
    message_template = '{entity} {object_id} not found'

    def __init__(self, object_id: UUID) -> None:
        super().__init__(self.message_template.format(entity=self.entity, object_id=object_id))


class AuthorNotFoundError(ObjectNotFoundError):
    entity = 'Author'


class GenreNotFoundError(ObjectNotFoundError):
    entity = 'Genre'


class UserNotFoundError(ObjectNotFoundError):
    entity = 'User'
