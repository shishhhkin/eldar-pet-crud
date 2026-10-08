import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.bootstrap import (
    build_cache,
    build_engine,
    build_library,
    build_library_http,
    build_membership_issuer,
    build_outbox,
    build_redis,
)
from src.config import Settings
from src.controllers.authors import router as authors_router
from src.controllers.genres import router as genres_router
from src.controllers.users import router as users_router
from src.exceptions.handlers import register_exception_handlers
from src.healthcheck.router import router as healthcheck_router
from src.infra.db import build_session_factory
from src.logging_config import setup_logging
from src.middleware import LoggingMiddleware, RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()  # type: ignore[call-arg]
    engine = build_engine(settings)
    client = build_redis(settings)
    http = build_library_http(settings)

    session_factory = build_session_factory(engine)
    cache = build_cache(settings, client)
    outbox = build_outbox(settings, session_factory, cache)
    library = build_library(settings, http)
    issuer = build_membership_issuer(settings, session_factory, library)

    app.state.session_factory = session_factory
    app.state.cache = cache
    app.state.outbox = outbox
    app.state.library = library
    app.state.membership_issuer = issuer
    outbox_worker = asyncio.create_task(outbox.run())

    yield

    outbox_worker.cancel()
    with suppress(asyncio.CancelledError):
        await outbox_worker

    await http.aclose()
    await client.aclose()
    await engine.dispose()


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
