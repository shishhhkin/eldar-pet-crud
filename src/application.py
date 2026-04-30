import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from src.controllers.authors import router as authors_router
from src.controllers.books import router as books_router
from src.controllers.genres import router as genres_router
from src.controllers.users import router as users_router
from src.exceptions import AppError
from src.healthcheck.router import router as healthcheck_router
from src.logging_config import setup_logging
from src.middleware import REQUEST_ID_HEADER, RequestIDMiddleware

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
        logger.warning('app_error code=%s status=%s msg=%s', exc.code, exc.status_code, exc.message)
        return _error_response(exc.status_code, exc.code, exc.message, rid)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        rid = getattr(request.state, 'request_id', None)
        logger.warning('integrity_error: %s', exc)
        return _error_response(
            status.HTTP_409_CONFLICT,
            'conflict',
            'Conflict: resource violates a uniqueness or relational constraint',
            rid,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, 'request_id', None)
        logger.exception('unhandled_error: %s', exc)
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
    v1_router.include_router(books_router)
    v1_router.include_router(genres_router)
    app.include_router(v1_router)

    return app
