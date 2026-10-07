import time

import pytest

from src.exceptions import TransientError
from src.utils.resilience import RetryPolicy, backoff_delay

ATTEMPTS = 3
BASE_DELAY = 0.001
MAX_DELAY = 0.004
RETRY_AFTER = 0.05
RETRY_AFTER_MAX_DELAY = 0.1
SAMPLES = 200


class Flaky:
    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.error = error or TransientError('boom')
        self.calls = 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return 'ok'


@pytest.fixture
def retry() -> RetryPolicy:
    return RetryPolicy(ATTEMPTS, BASE_DELAY, MAX_DELAY)


@pytest.mark.parametrize('attempt', range(6))
def test_backoff_delay_stays_within_exponential_cap(attempt: int) -> None:
    ceiling = min(MAX_DELAY, BASE_DELAY * 2**attempt)

    delays = [backoff_delay(attempt, BASE_DELAY, MAX_DELAY) for _ in range(SAMPLES)]

    assert all(0 <= delay <= ceiling for delay in delays)
    assert len(set(delays)) > 1


async def test_retry_recovers_after_transient_failures(retry: RetryPolicy) -> None:
    fn = Flaky(ATTEMPTS - 1)

    assert await retry.call(fn) == 'ok'
    assert fn.calls == ATTEMPTS


async def test_retry_gives_up_after_all_attempts(retry: RetryPolicy) -> None:
    fn = Flaky(ATTEMPTS)

    with pytest.raises(TransientError):
        await retry.call(fn)

    assert fn.calls == ATTEMPTS


@pytest.mark.parametrize('error', [ValueError('bug'), LookupError('missing')])
async def test_retry_does_not_repeat_non_transient_errors(
    retry: RetryPolicy, error: Exception
) -> None:
    fn = Flaky(ATTEMPTS, error)

    with pytest.raises(type(error)):
        await retry.call(fn)

    assert fn.calls == 1


async def test_retry_waits_retry_after_instead_of_backoff() -> None:
    retry = RetryPolicy(ATTEMPTS, BASE_DELAY, RETRY_AFTER_MAX_DELAY)
    fn = Flaky(1, TransientError('throttled', retry_after=RETRY_AFTER))
    started = time.monotonic()

    assert await retry.call(fn) == 'ok'

    assert time.monotonic() - started >= RETRY_AFTER
    assert fn.calls == 2


async def test_retry_gives_up_when_retry_after_exceeds_max_delay(retry: RetryPolicy) -> None:
    fn = Flaky(1, TransientError('throttled', retry_after=MAX_DELAY * 2))

    with pytest.raises(TransientError):
        await retry.call(fn)

    assert fn.calls == 1
