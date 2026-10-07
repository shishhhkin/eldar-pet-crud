import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

from src.exceptions import TransientError

logger = logging.getLogger(__name__)


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
                delay = self._delay(attempt, exc.retry_after)
                if delay is None:
                    logger.warning('transient failure (%s), retry-after exceeds max delay', exc)
                    raise
                logger.warning(
                    'transient failure (%s), retry %d/%d in %.3fs',
                    exc,
                    attempt,
                    self.attempts - 1,
                    delay,
                )
                await asyncio.sleep(delay)
        return await fn()

    def _delay(self, attempt: int, retry_after: float | None) -> float | None:
        if retry_after is None:
            return backoff_delay(attempt - 1, self.base_delay, self.max_delay)
        if retry_after > self.max_delay:
            return None
        return retry_after
