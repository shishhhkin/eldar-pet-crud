from http import HTTPStatus


class AppError(Exception):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    code = 'internal_error'

    def __init__(self, message: str = 'Internal server error') -> None:
        self.message = message
        super().__init__(message)
