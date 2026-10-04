from http import HTTPStatus

from src.exceptions.base import AppError


class LibraryUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = 'library_unavailable'
    default_message = 'Library service unavailable'
