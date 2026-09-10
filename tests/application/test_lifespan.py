import asyncio
from typing import Any

import pytest
from fastapi import FastAPI

from src import application
from src.application import lifespan
from src.config import Settings

DRAIN_TIMEOUT_SECONDS = 2.0
FAST_RETRY_SECONDS = '0.01'


class _Recorder:
    def __init__(self) -> None:
        self.closed = False
        self.kwargs: dict[str, Any] = {}
        self.sets: list[str] = []

    def capture(self, **kwargs: object) -> _Recorder:
        self.kwargs = kwargs
        return self

    async def set(self, key: str, *args: object, **kwargs: object) -> None:
        self.sets.append(key)

    async def aclose(self) -> None:
        self.closed = True

    async def dispose(self) -> None:
        self.closed = True


@pytest.fixture
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@pytest.fixture
def engine_recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(
        application,
        'create_async_engine',
        lambda url, **kwargs: recorder.capture(url=url, **kwargs),
    )
    return recorder


@pytest.fixture
def redis_recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(application, 'Redis', lambda **kwargs: recorder.capture(**kwargs))
    return recorder


async def test_startup_publishes_resources_on_app_state(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
    settings: Settings,
) -> None:
    app = FastAPI()

    async with lifespan(app):
        assert app.state.session_factory.kw['bind'] is engine_recorder
        assert app.state.cache.client is redis_recorder
        assert app.state.cache.ttl_seconds == settings.cache_ttl_seconds
        assert app.state.cache.tombstone_ttl_ms == settings.cache_tombstone_ttl_ms
        assert app.state.cache.invalidation_attempts == settings.cache_invalidation_attempts

        invalidations = app.state.cache.invalidations
        assert invalidations.max_size == settings.cache_invalidation_queue_size
        assert invalidations.retry_interval_seconds == settings.cache_invalidation_retry_seconds


async def test_startup_builds_engine_from_settings(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
    settings: Settings,
) -> None:
    async with lifespan(FastAPI()):
        assert engine_recorder.kwargs['url'] == str(settings.postgres_url)


async def test_startup_builds_redis_client_from_settings(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
    settings: Settings,
) -> None:
    async with lifespan(FastAPI()):
        assert redis_recorder.kwargs['host'] == settings.redis_host
        assert redis_recorder.kwargs['port'] == settings.redis_port
        assert redis_recorder.kwargs['socket_connect_timeout'] == settings.redis_timeout_seconds
        assert redis_recorder.kwargs['socket_timeout'] == settings.redis_timeout_seconds


async def test_startup_passes_configured_retries_to_redis_client(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retries = 7
    monkeypatch.setenv('redis_retries', str(retries))

    async with lifespan(FastAPI()):
        assert redis_recorder.kwargs['retry'].get_retries() == retries


async def test_shutdown_closes_redis_and_engine(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
) -> None:
    async with lifespan(FastAPI()):
        assert not engine_recorder.closed
        assert not redis_recorder.closed

    assert engine_recorder.closed
    assert redis_recorder.closed


def _invalidator_tasks() -> list[asyncio.Task[None]]:
    return [
        task
        for task in asyncio.all_tasks()
        if task.get_coro().__qualname__ == 'InvalidationQueue.run'  # type: ignore[union-attr]
    ]


async def test_startup_runs_invalidator_and_stops_it_on_shutdown(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
) -> None:
    async with lifespan(FastAPI()):
        assert len(_invalidator_tasks()) == 1

    assert _invalidator_tasks() == []


async def test_invalidator_drains_held_keys_through_the_cache(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('cache_invalidation_retry_seconds', FAST_RETRY_SECONDS)
    key = 'v1:author:queued'
    app = FastAPI()

    async with lifespan(app):
        app.state.cache.invalidations.hold(key)
        async with asyncio.timeout(DRAIN_TIMEOUT_SECONDS):
            while app.state.cache.invalidations.holds(key):
                await asyncio.sleep(float(FAST_RETRY_SECONDS))

    assert redis_recorder.sets == [key]
