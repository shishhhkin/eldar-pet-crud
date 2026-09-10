import asyncio
import logging

import pytest

from src.infra.invalidation import InvalidationQueue

LOGGER_NAME = 'src.infra.invalidation'

QUEUE_SIZE = 10
RETRY_SECONDS = 0.01
DRAIN_TIMEOUT_SECONDS = 2.0


class _Tombstones:
    def __init__(self, failing: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.failing = failing or set()

    async def __call__(self, key: str) -> bool:
        self.calls.append(key)
        return key not in self.failing


def _errors(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == LOGGER_NAME]


def test_held_key_is_reported_until_released() -> None:
    queue = InvalidationQueue(QUEUE_SIZE, RETRY_SECONDS)
    key = 'v1:author:1'

    queue.hold(key)
    assert queue.holds(key)

    queue.release(key)
    assert not queue.holds(key)


def test_repeated_hold_does_not_grow_queue(caplog: pytest.LogCaptureFixture) -> None:
    queue = InvalidationQueue(1, RETRY_SECONDS)
    key = 'v1:author:1'
    queue.hold(key)

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        queue.hold(key)

    assert len(queue.keys) == 1
    assert queue.holds(key)
    assert _errors(caplog) == []


def test_full_queue_drops_oldest_key_and_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    queue = InvalidationQueue(1, RETRY_SECONDS)
    queue.hold('v1:author:old')

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        queue.hold('v1:author:new')

    assert not queue.holds('v1:author:old')
    assert queue.holds('v1:author:new')

    records = _errors(caplog)
    assert len(records) == 1
    assert 'v1:author:old' in records[0].getMessage()


async def test_drain_tombstones_every_held_key() -> None:
    queue = InvalidationQueue(QUEUE_SIZE, RETRY_SECONDS)
    keys = ['v1:author:1', 'v1:author:2']
    for key in keys:
        queue.hold(key)
    tombstones = _Tombstones()

    await queue.drain(tombstones)

    assert tombstones.calls == keys
    assert queue.keys == {}


async def test_drain_stops_at_first_failure() -> None:
    queue = InvalidationQueue(QUEUE_SIZE, RETRY_SECONDS)
    queue.hold('v1:author:1')
    queue.hold('v1:author:2')
    tombstones = _Tombstones({'v1:author:1'})

    await queue.drain(tombstones)

    assert tombstones.calls == ['v1:author:1']
    assert queue.holds('v1:author:1')
    assert queue.holds('v1:author:2')


async def test_drain_keeps_only_the_key_whose_tombstone_failed() -> None:
    queue = InvalidationQueue(QUEUE_SIZE, RETRY_SECONDS)
    queue.hold('v1:author:1')
    queue.hold('v1:author:2')
    tombstones = _Tombstones({'v1:author:2'})

    await queue.drain(tombstones)

    assert not queue.holds('v1:author:1')
    assert queue.holds('v1:author:2')


async def test_close_stays_quiet_when_queue_drains(caplog: pytest.LogCaptureFixture) -> None:
    queue = InvalidationQueue(QUEUE_SIZE, RETRY_SECONDS)
    key = 'v1:author:1'
    queue.hold(key)

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        await queue.close(_Tombstones())

    assert not queue.holds(key)
    assert _errors(caplog) == []


async def test_close_logs_error_for_keys_left_in_queue(caplog: pytest.LogCaptureFixture) -> None:
    queue = InvalidationQueue(QUEUE_SIZE, RETRY_SECONDS)
    key = 'v1:author:1'
    queue.hold(key)

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        await queue.close(_Tombstones({key}))

    assert queue.holds(key)

    records = _errors(caplog)
    assert len(records) == 1
    assert key in records[0].getMessage()


async def test_run_drains_on_interval_and_cancels_cleanly() -> None:
    queue = InvalidationQueue(QUEUE_SIZE, RETRY_SECONDS)
    key = 'v1:author:1'
    queue.hold(key)
    tombstones = _Tombstones()

    task = asyncio.create_task(queue.run(tombstones))
    async with asyncio.timeout(DRAIN_TIMEOUT_SECONDS):
        while queue.holds(key):
            await asyncio.sleep(RETRY_SECONDS)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert tombstones.calls == [key]
