from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from src.controllers.authors import router as authors_router
from src.controllers.books import router as books_router
from src.controllers.genres import router as genres_router
from src.controllers.users import router as users_router
from src.healthcheck.router import router as healthcheck_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def get_app() -> FastAPI:
    app = FastAPI(
        docs_url='/docs',
        openapi_url='/openapi.json',
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={'detail': 'Conflict: resource violates a uniqueness or relational constraint'},
        )

    app.include_router(healthcheck_router)
    app.include_router(users_router)
    app.include_router(authors_router)
    app.include_router(books_router)
    app.include_router(genres_router)

    return app