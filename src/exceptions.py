from uuid import UUID


class AppError(Exception):
    status_code = 500
    code = 'internal_error'

    def __init__(self, message: str = 'Internal server error') -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    code = 'not_found'


class ValidationAppError(AppError):
    status_code = 422
    code = 'validation_error'


class ConflictError(AppError):
    status_code = 409
    code = 'conflict'


class AuthorNotFound(NotFoundError):
    def __init__(self, author_id: UUID) -> None:
        super().__init__(f'Author {author_id} not found')


class BookNotFound(NotFoundError):
    def __init__(self, book_id: UUID) -> None:
        super().__init__(f'Book {book_id} not found')


class GenreNotFound(NotFoundError):
    def __init__(self, genre_id: UUID) -> None:
        super().__init__(f'Genre {genre_id} not found')


class UserNotFound(NotFoundError):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f'User {user_id} not found')


class GenresNotFound(ValidationAppError):
    def __init__(self, missing: list[UUID] | list[str]) -> None:
        super().__init__(f'genres not found: {[str(x) for x in missing]}')
