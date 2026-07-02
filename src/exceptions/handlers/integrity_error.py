import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from src.exceptions.handlers.response import error_response

logger = logging.getLogger(__name__)


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    rid = getattr(request.state, 'request_id', None)
    orig = exc.orig
    diag = getattr(orig, 'diag', None)
    sqlstate = getattr(orig, 'sqlstate', None)
    constraint = getattr(diag, 'constraint_name', None) if diag else None
    table = getattr(diag, 'table_name', None) if diag else None
    detail = getattr(diag, 'message_detail', None) if diag else None

    client_caused = sqlstate in {'23505', '23503', '23514'}
    logger.log(
        logging.WARNING if client_caused else logging.ERROR,
        'integrity_error: %s %s sqlstate=%s constraint=%s table=%s detail=%s',
        request.method,
        request.url.path,
        sqlstate,
        constraint,
        table,
        detail,
        exc_info=True,
    )

    return error_response(
        status.HTTP_409_CONFLICT,
        'conflict',
        'Conflict: resource violates a uniqueness or relational constraint',
        rid,
    )
