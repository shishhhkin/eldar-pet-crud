import pytest
from fastapi import FastAPI

from src import cache as cache_module
from src import db as db_module
from src.application import lifespan


class _Recorder:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True

    async def dispose(self) -> None:
        self.closed = True


@pytest.fixture
def redis_recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(cache_module, 'client', recorder)
    return recorder


@pytest.fixture
def engine_recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(db_module, 'engine', recorder)
    return recorder


async def test_shutdown_closes_redis_and_engine(
    redis_recorder: _Recorder,
    engine_recorder: _Recorder,
) -> None:
    async with lifespan(FastAPI()):
        assert not redis_recorder.closed
        assert not engine_recorder.closed

    assert redis_recorder.closed
    assert engine_recorder.closed
