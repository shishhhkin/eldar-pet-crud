from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.controllers.authors import router as authors_router
from src.controllers.genres import router as genres_router
from src.controllers.users import router as users_router
from src.exceptions.handlers import register_exception_handlers
from src.healthcheck.router import router as healthcheck_router
from src.logging_config import setup_logging
from src.middleware import LoggingMiddleware, RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


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

    register_exception_handlers(app)

    app.include_router(healthcheck_router)

    v1_router = APIRouter(prefix='/v1')
    v1_router.include_router(users_router)
    v1_router.include_router(authors_router)
    v1_router.include_router(genres_router)
    app.include_router(v1_router)

    return app
