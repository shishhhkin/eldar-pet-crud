from http import HTTPStatus

from src.exceptions.base import AppError


class ExternalServiceUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = 'external_service_unavailable'
    default_message = 'External service unavailable'


class ExternalServiceBadResponseError(AppError):
    status_code = HTTPStatus.BAD_GATEWAY
    code = 'external_service_bad_response'
    default_message = 'External service returned an unexpected response'
