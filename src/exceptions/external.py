from http import HTTPStatus

from src.exceptions.base import AppError


class ExternalServiceUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = 'external_service_unavailable'
    default_message = 'External service unavailable'
