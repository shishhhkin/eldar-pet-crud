import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import Settings
from src.controllers.authors import router as authors_router
from src.controllers.genres import router as genres_router
from src.controllers.users import router as users_router
from src.exceptions.handlers import register_exception_handlers
from src.healthcheck.router import router as healthcheck_router
from src.infra.cache import Cache
from src.infra.db import build_session_factory
from src.infra.invalidation import InvalidationOutbox
from src.logging_config import setup_logging
from src.middleware import LoggingMiddleware, RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()  # type: ignore[call-arg]
    engine = create_async_engine(str(settings.postgres_url), pool_pre_ping=True)
    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        socket_connect_timeout=settings.redis_timeout_seconds,
        socket_timeout=settings.redis_timeout_seconds,
        retry=Retry(NoBackoff(), settings.redis_retries),
    )

    session_factory = build_session_factory(engine)
    cache = Cache(client, settings.cache_ttl_seconds, settings.cache_tombstone_ttl_ms)
    outbox = InvalidationOutbox(
        session_factory,
        cache,
        settings.cache_invalidation_batch_size,
        settings.cache_invalidation_retry_seconds,
        settings.cache_invalidation_lease_seconds,
    )

    app.state.session_factory = session_factory
    app.state.cache = cache
    app.state.outbox = outbox
    invalidator = asyncio.create_task(outbox.run())

    yield

    invalidator.cancel()
    with suppress(asyncio.CancelledError):
        await invalidator

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
