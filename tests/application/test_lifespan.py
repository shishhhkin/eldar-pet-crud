import pytest
from fastapi import FastAPI

from src import application
from src.application import lifespan
from src.config import Settings


class _Recorder:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def dispose(self) -> None:
        self.closed = True


@pytest.fixture
def engine_recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(application, 'build_engine', lambda url: recorder)
    return recorder


@pytest.fixture
def redis_recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(application, 'build_client', lambda host, port: recorder)
    return recorder


async def test_startup_publishes_resources_on_app_state(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
) -> None:
    app = FastAPI()

    async with lifespan(app):
        assert app.state.session_factory.kw['bind'] is engine_recorder
        assert app.state.cache.client is redis_recorder
        assert app.state.cache.ttl_seconds == Settings().cache_ttl_seconds  # type: ignore[call-arg]


async def test_shutdown_closes_redis_and_engine(
    engine_recorder: _Recorder,
    redis_recorder: _Recorder,
) -> None:
    async with lifespan(FastAPI()):
        assert not engine_recorder.closed
        assert not redis_recorder.closed

    assert engine_recorder.closed
    assert redis_recorder.closed
