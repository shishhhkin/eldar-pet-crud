import asyncio
import os
import signal
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

ROOT = Path(__file__).resolve().parent.parent
STARTED = 'membership worker started'
STOPPED = 'membership worker stopped'
PROCESS_TIMEOUT_SECONDS = 15.0
POLL_SECONDS = 0.05


def worker_env(
    postgres: PostgresContainer, redis: RedisContainer, library_url: str
) -> dict[str, str]:
    return {
        **os.environ,
        'postgres_user': postgres.username,
        'postgres_password': postgres.password,
        'postgres_host': postgres.get_container_host_ip(),
        'postgres_port': str(postgres.get_exposed_port(5432)),
        'postgres_db': postgres.dbname,
        'redis_host': redis.get_container_host_ip(),
        'redis_port': str(redis.get_exposed_port(6379)),
        'library_url': library_url,
        'membership_sync_interval_seconds': str(POLL_SECONDS),
    }


class WorkerProcess:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.log: list[str] = []
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        assert self.process.stderr is not None
        async for line in self.process.stderr:
            self.log.append(line.decode())

    def logged(self, text: str) -> bool:
        return any(text in line for line in self.log)

    async def wait_for(self, text: str) -> None:
        async with asyncio.timeout(PROCESS_TIMEOUT_SECONDS):
            while not self.logged(text):
                if self._reader.done():
                    raise AssertionError(f'worker exited before {text!r}:\n{"".join(self.log)}')
                await asyncio.sleep(POLL_SECONDS)

    async def stop(self) -> int:
        self.process.send_signal(signal.SIGTERM)
        async with asyncio.timeout(PROCESS_TIMEOUT_SECONDS):
            await self._reader
            return await self.process.wait()


@asynccontextmanager
async def running_worker(env: dict[str, str]) -> AsyncIterator[WorkerProcess]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        '-m',
        'src.worker',
        cwd=ROOT,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    worker = WorkerProcess(process)
    try:
        await worker.wait_for(STARTED)
        yield worker
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
