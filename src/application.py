import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from src.controllers.authors import router as authors_router
from src.controllers.genres import router as genres_router
from src.controllers.users import router as users_router
from src.exceptions import AppError
from src.healthcheck.router import router as healthcheck_router
from src.logging_config import setup_logging
from src.middleware import REQUEST_ID_HEADER, LoggingMiddleware, RequestIDMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def _error_response(status_code: int, code: str, detail: str, rid: str | None) -> JSONResponse:
    headers = {REQUEST_ID_HEADER: rid} if rid else None
    return JSONResponse(
        status_code=status_code,
        content={'code': code, 'detail': detail, 'request_id': rid},
        headers=headers,
    )


def get_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        docs_url='/docs',
        openapi_url='/openapi.json',
        lifespan=lifespan,
    )

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        rid = getattr(request.state, 'request_id', None)
        logger.info(
            'app_error: code=%s status=%s detail=%s',
            exc.code,
            exc.status_code.value,
            exc.message,
        )
        return _error_response(exc.status_code.value, exc.code, exc.message, rid)

    @app.exception_handler(IntegrityError)
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

        return _error_response(
            status.HTTP_409_CONFLICT,
            'conflict',
            'Conflict: resource violates a uniqueness or relational constraint',
            rid,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, 'request_id', None)
        logger.exception('unhandled exception: %s', type(exc).__name__)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            'internal_error',
            'Internal server error',
            rid,
        )

    app.include_router(healthcheck_router)

    v1_router = APIRouter(prefix='/v1')
    v1_router.include_router(users_router)
    v1_router.include_router(authors_router)
    v1_router.include_router(genres_router)
    app.include_router(v1_router)

    return app
