import asyncio
import logging
import signal
import sys
import tempfile
import time
from pathlib import Path

from src.bootstrap import build_book_reservation_relay, build_engine, build_kafka_producer
from src.config import Settings
from src.infra.db import build_session_factory
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

HEARTBEAT_NAME = 'book-reservation-relay.heartbeat'


def heartbeat_path() -> Path:
    return Path(tempfile.gettempdir()) / HEARTBEAT_NAME


async def serve() -> None:
    settings = Settings()  # type: ignore[call-arg]
    engine = build_engine(settings)
    producer = build_kafka_producer(settings)
    session = build_session_factory(engine)()
    relay = build_book_reservation_relay(settings, session, producer, heartbeat_path().touch)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, relay.stop)
    try:
        await producer.start()
        logger.info('book reservation relay started')
        await relay.run()
    finally:
        try:
            async with asyncio.timeout(settings.kafka_send_timeout_seconds):
                await producer.stop()
        except TimeoutError:
            logger.warning('kafka producer stop timed out, unsent reservations stay in outbox')
        await session.close()
        await engine.dispose()
    logger.info('book reservation relay stopped')


def is_alive(settings: Settings) -> bool:
    max_age = (
        settings.book_reservation_relay_interval_seconds
        + settings.book_reservation_relay_lease_seconds
    )
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
