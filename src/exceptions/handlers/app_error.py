import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from src.exceptions import AppError
from src.exceptions.handlers.response import error_response

logger = logging.getLogger(__name__)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = getattr(request.state, 'request_id', None)
    logger.info(
        'app_error: code=%s status=%s detail=%s',
        exc.code,
        exc.status_code.value,
        exc.message,
    )
    return error_response(exc.status_code.value, exc.code, exc.message, rid)
