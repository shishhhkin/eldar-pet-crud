import asyncio

import pytest

from src.exceptions import CircuitOpenError, TransientError
from src.utils.resilience import CircuitBreaker, RetryPolicy, backoff_delay

ATTEMPTS = 3
BASE_DELAY = 0.001
MAX_DELAY = 0.004
THRESHOLD = 2
RESET_SECONDS = 0.05
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


@pytest.fixture
def fast_breaker() -> CircuitBreaker:
    return CircuitBreaker(THRESHOLD, RESET_SECONDS)


async def _open(breaker: CircuitBreaker) -> None:
    for _ in range(THRESHOLD):
        with pytest.raises(TransientError):
            await breaker.call(Flaky(1))


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


@pytest.mark.parametrize('error', [ValueError('bug'), CircuitOpenError('open')])
async def test_retry_does_not_repeat_non_transient_errors(
    retry: RetryPolicy, error: Exception
) -> None:
    fn = Flaky(ATTEMPTS, error)

    with pytest.raises(type(error)):
        await retry.call(fn)

    assert fn.calls == 1


async def test_breaker_opens_after_threshold_and_skips_calls(
    fast_breaker: CircuitBreaker,
) -> None:
    await _open(fast_breaker)
    fn = Flaky(0)

    with pytest.raises(CircuitOpenError):
        await fast_breaker.call(fn)

    assert fn.calls == 0


async def test_breaker_success_resets_failure_count(fast_breaker: CircuitBreaker) -> None:
    for _ in range(THRESHOLD + 1):
        with pytest.raises(TransientError):
            await fast_breaker.call(Flaky(1))
        assert await fast_breaker.call(Flaky(0)) == 'ok'


async def test_breaker_counts_any_error_as_failure(fast_breaker: CircuitBreaker) -> None:
    for _ in range(THRESHOLD):
        with pytest.raises(ValueError):
            await fast_breaker.call(Flaky(1, ValueError('bug')))

    with pytest.raises(CircuitOpenError):
        await fast_breaker.call(Flaky(0))


async def test_half_open_probe_success_closes_breaker(fast_breaker: CircuitBreaker) -> None:
    await _open(fast_breaker)
    await asyncio.sleep(RESET_SECONDS)

    assert await fast_breaker.call(Flaky(0)) == 'ok'
    assert await fast_breaker.call(Flaky(0)) == 'ok'


async def test_half_open_probe_failure_reopens_breaker(fast_breaker: CircuitBreaker) -> None:
    await _open(fast_breaker)
    await asyncio.sleep(RESET_SECONDS)

    with pytest.raises(TransientError):
        await fast_breaker.call(Flaky(1))
    fn = Flaky(0)
    with pytest.raises(CircuitOpenError):
        await fast_breaker.call(fn)

    assert fn.calls == 0


async def test_half_open_lets_single_probe_through(fast_breaker: CircuitBreaker) -> None:
    await _open(fast_breaker)
    await asyncio.sleep(RESET_SECONDS)
    release = asyncio.Event()

    async def slow_probe() -> str:
        await release.wait()
        return 'ok'

    probe = asyncio.create_task(fast_breaker.call(slow_probe))
    await asyncio.sleep(0)
    with pytest.raises(CircuitOpenError):
        await fast_breaker.call(Flaky(0))
    release.set()

    assert await probe == 'ok'


async def test_cancelled_probe_releases_half_open_slot(fast_breaker: CircuitBreaker) -> None:
    await _open(fast_breaker)
    await asyncio.sleep(RESET_SECONDS)

    probe = asyncio.create_task(fast_breaker.call(asyncio.Event().wait))
    await asyncio.sleep(0)
    probe.cancel()
    with pytest.raises(asyncio.CancelledError):
        await probe

    assert await fast_breaker.call(Flaky(0)) == 'ok'
