from http import HTTPStatus
from uuid import UUID

from src.exceptions.base import AppError


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = 'not_found'


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
