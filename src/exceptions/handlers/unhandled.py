import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.exceptions.handlers.response import error_response

logger = logging.getLogger(__name__)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, 'request_id', None)
    logger.exception('unhandled exception: %s', type(exc).__name__)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        'internal_error',
        'Internal server error',
        rid,
    )
