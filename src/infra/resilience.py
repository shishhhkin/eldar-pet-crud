import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class TransientError(Exception):
    pass


class CircuitOpenError(Exception):
    pass


def backoff_delay(attempt: int, base: float, cap: float) -> float:
    return random.uniform(0, min(cap, base * 2**attempt))


class RetryPolicy:
    def __init__(self, attempts: int, base_delay: float, max_delay: float) -> None:
        self.attempts = attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def call[T](self, fn: Callable[[], Awaitable[T]]) -> T:
        for attempt in range(1, self.attempts):
            try:
                return await fn()
            except TransientError as exc:
                delay = backoff_delay(attempt - 1, self.base_delay, self.max_delay)
                logger.warning(
                    'transient failure (%s), retry %d/%d in %.3fs',
                    exc,
                    attempt,
                    self.attempts - 1,
                    delay,
                )
                await asyncio.sleep(delay)
        return await fn()


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_seconds: float) -> None:
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False

    async def call[T](self, fn: Callable[[], Awaitable[T]]) -> T:
        probe = self._acquire()
        try:
            result = await fn()
        except Exception:
            self._record_failure()
            raise
        finally:
            if probe:
                self._probing = False
        self._record_success()
        return result

    def _acquire(self) -> bool:
        if self._opened_at is None:
            return False
        if self._probing or time.monotonic() - self._opened_at < self.reset_seconds:
            raise CircuitOpenError('circuit is open')
        self._probing = True
        return True

    def _record_failure(self) -> None:
        self._failures += 1
        if self._opened_at is not None or self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()
            logger.warning('circuit opened after %d consecutive failures', self._failures)

    def _record_success(self) -> None:
        if self._opened_at is not None:
            logger.info('circuit closed')
        self._failures = 0
        self._opened_at = None
