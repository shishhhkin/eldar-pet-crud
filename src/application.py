# --- Устаревший вариант ---
# from fastapi import FastAPI
# from fastapi.responses import UJSONResponse  # UJSONResponse — deprecated
# from starlette.middleware.cors import CORSMiddleware  # непрямой импорт
# from healthcheck.router import router  # относительный импорт без пакета src
#
#
# def get_app() -> FastAPI:
#     app = FastAPI(
#         docs_url='/docs',
#         openapi_url='/openapi.json',
#         default_response_class=UJSONResponse,
#     )
#
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=['*'],
#         allow_credentials=True,
#         allow_methods=['*'],
#         allow_headers=['*'],
#     )
#     app.include_router(router)
#     return app
# ---------------------------

# Актуальный подход:
# - UJSONResponse больше не нужен: по докам FastAPI Pydantic v2 сериализует
#   напрямую в JSON-байты на Rust (через response_model / return type hints),
#   это быстрее и не требует кастомного response_class.
# - CORSMiddleware импортируется из fastapi.middleware.cors (канонический путь).
# - Модули импортируются от корня пакета `src.*`, это устойчиво к CWD/reload.
# - Жизненный цикл приложения управляется через `lifespan` (on_event устарел).
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
    # место для инициализации ресурсов (пул БД, кэш, клиенты).
    yield
    # место для корректного закрытия ресурсов.


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    app = FastAPI(
        docs_url='/docs',
        openapi_url='/openapi.json',
        lifespan=lifespan,
        # default_response_class НЕ указываем — пусть работает встроенная
        # быстрая сериализация через Pydantic/response_model.
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
