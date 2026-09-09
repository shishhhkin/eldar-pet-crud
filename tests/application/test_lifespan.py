from typing import Any

import pytest
from fastapi import FastAPI

from src import application
from src.application import lifespan
from src.config import Settings


class _Recorder:
    def __init__(self) -> None:
        self.closed = False
        self.kwargs: dict[str, Any] = {}

    def capture(self, **kwargs: object) -> _Recorder:
        self.kwargs = kwargs
        return self

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
