import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

type Tombstone = Callable[[str], Awaitable[bool]]


class InvalidationQueue:
    def __init__(self, max_size: int, retry_interval_seconds: float) -> None:
        self.max_size = max_size
        self.retry_interval_seconds = retry_interval_seconds
        self.keys: dict[str, None] = {}

    def hold(self, key: str) -> None:
        if key not in self.keys and len(self.keys) >= self.max_size:
            dropped = next(iter(self.keys))
            del self.keys[dropped]
            logger.error('cache invalidation dropped, queue is full: %s', dropped)
        self.keys[key] = None

    def holds(self, key: str) -> bool:
        return key in self.keys

    def release(self, key: str) -> None:
        self.keys.pop(key, None)

    async def drain(self, tombstone: Tombstone) -> None:
        for key in list(self.keys):
            if not await tombstone(key):
                return
            self.release(key)

    async def run(self, tombstone: Tombstone) -> None:
        while True:
            await asyncio.sleep(self.retry_interval_seconds)
            await self.drain(tombstone)

    async def close(self, tombstone: Tombstone) -> None:
        await self.drain(tombstone)
        if self.keys:
            logger.error('cache invalidation lost on shutdown: %s', ', '.join(self.keys))
