from http import HTTPStatus


class AppError(Exception):
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    code = 'internal_error'
    default_message = 'Internal server error'

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)
