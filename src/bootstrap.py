from datetime import timedelta

import httpx
from aiobreaker import CircuitBreaker
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.clients.library import LibraryClient
from src.config import Settings
from src.infra.cache import Cache
from src.repository import CacheInvalidationRepo, MembershipRequestRepo, UserMembershipRepo
from src.services.invalidation_outbox import InvalidationOutbox
from src.services.membership_issuer import MembershipIssuer
from src.utils.resilience import RetryPolicy


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(str(settings.postgres_url), pool_pre_ping=True)


def build_redis(settings: Settings) -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        socket_connect_timeout=settings.redis_timeout_seconds,
        socket_timeout=settings.redis_timeout_seconds,
        retry=Retry(NoBackoff(), settings.redis_retries),
    )


def build_cache(settings: Settings, client: Redis) -> Cache:
    return Cache(client, settings.cache_ttl_seconds, settings.cache_tombstone_ttl_ms)


def build_outbox(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    cache: Cache,
) -> InvalidationOutbox:
    return InvalidationOutbox(
        session_factory,
        CacheInvalidationRepo,
        cache,
        settings.cache_invalidation_batch_size,
        settings.cache_invalidation_retry_seconds,
        settings.cache_invalidation_lease_seconds,
    )


def build_library_http(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=str(settings.library_url),
        timeout=settings.library_timeout_seconds,
        trust_env=False,
    )


def build_library(settings: Settings, http: httpx.AsyncClient) -> LibraryClient:
    return LibraryClient(
        http,
        RetryPolicy(
            settings.library_retry_attempts,
            settings.library_retry_base_delay_seconds,
            settings.library_retry_max_delay_seconds,
        ),
        CircuitBreaker(
            fail_max=settings.library_breaker_failure_threshold,
            timeout_duration=timedelta(seconds=settings.library_breaker_reset_seconds),
        ),
        settings.library_timeout_seconds,
    )


def build_membership_issuer(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    library: LibraryClient,
) -> MembershipIssuer:
    return MembershipIssuer(
        session_factory,
        UserMembershipRepo,
        MembershipRequestRepo,
        library,
        settings.membership_sync_pass_limit,
        settings.membership_sync_interval_seconds,
        settings.membership_sync_lease_seconds,
        settings.membership_sync_retry_base_delay_seconds,
        settings.membership_sync_retry_max_delay_seconds,
    )
