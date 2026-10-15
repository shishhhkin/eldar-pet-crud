import asyncio
import logging
import signal
import sys
import tempfile
import time
from pathlib import Path

from src.bootstrap import (
    build_engine,
    build_library,
    build_library_http,
    build_membership_service,
)
from src.config import Settings
from src.infra.db import build_session_factory
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

HEARTBEAT_NAME = 'membership-worker.heartbeat'


def heartbeat_path() -> Path:
    return Path(tempfile.gettempdir()) / HEARTBEAT_NAME


async def serve() -> None:
    settings = Settings()  # type: ignore[call-arg]
    engine = build_engine(settings)
    http = build_library_http(settings)
    membership_service = build_membership_service(
        settings,
        build_session_factory(engine),
        build_library(settings, http),
        heartbeat_path().touch,
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, membership_service.stop)
    logger.info('membership worker started')
    try:
        await membership_service.run()
    finally:
        await http.aclose()
        await engine.dispose()
    logger.info('membership worker stopped')


def is_alive(settings: Settings) -> bool:
    max_age = settings.membership_sync_interval_seconds + settings.membership_sync_lease_seconds
    try:
        age = time.time() - heartbeat_path().stat().st_mtime
    except FileNotFoundError:
        return False
    return age <= max_age


def main() -> None:
    if sys.argv[1:] == ['healthcheck']:
        sys.exit(0 if is_alive(Settings()) else 1)  # type: ignore[call-arg]
    setup_logging()
    asyncio.run(serve())


if __name__ == '__main__':
    main()
