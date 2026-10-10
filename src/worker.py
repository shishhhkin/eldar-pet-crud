import asyncio
import logging
import signal

from src.bootstrap import (
    build_engine,
    build_library,
    build_library_http,
    build_membership_issuer,
)
from src.config import Settings
from src.infra.db import build_session_factory
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def serve() -> None:
    settings = Settings()  # type: ignore[call-arg]
    engine = build_engine(settings)
    http = build_library_http(settings)
    issuer = build_membership_issuer(
        settings, build_session_factory(engine), build_library(settings, http)
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, issuer.stop)
    logger.info('membership worker started')
    try:
        await issuer.run()
    finally:
        await http.aclose()
        await engine.dispose()
    logger.info('membership worker stopped')


def main() -> None:
    setup_logging()
    asyncio.run(serve())


if __name__ == '__main__':
    main()
