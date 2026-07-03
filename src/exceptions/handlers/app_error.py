from fastapi import Request
from fastapi.responses import JSONResponse

from src.exceptions import AppError
from src.exceptions.handlers.response import error_response


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = getattr(request.state, 'request_id', None)
    return error_response(exc.status_code.value, exc.code, exc.message, rid)
