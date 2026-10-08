from collections.abc import Callable

import pytest
from pydantic import ValidationError

from src.config import Settings

type LoadSettings = Callable[..., Settings]

BASE_ENV = {
    'postgres_user': 'app',
    'postgres_password': 'password',
    'postgres_host': 'localhost',
    'postgres_port': '5432',
    'postgres_db': 'app',
    'redis_host': 'localhost',
    'redis_port': '6379',
    'redis_timeout_seconds': '0.5',
    'redis_retries': '1',
    'cache_ttl_seconds': '3600',
    'cache_tombstone_ttl_ms': '2000',
    'cache_invalidation_retry_seconds': '5',
    'cache_invalidation_batch_size': '100',
    'cache_invalidation_lease_seconds': '60',
    'library_url': 'http://localhost:8001/v1',
    'library_timeout_seconds': '1',
    'library_retry_attempts': '3',
    'library_retry_base_delay_seconds': '0.1',
    'library_retry_max_delay_seconds': '1',
    'library_breaker_failure_threshold': '5',
    'library_breaker_reset_seconds': '10',
    'membership_sync_interval_seconds': '5',
    'membership_sync_pass_limit': '100',
    'membership_sync_lease_seconds': '60',
    'membership_sync_retry_base_delay_seconds': '5',
    'membership_sync_retry_max_delay_seconds': '3600',
}

NON_EMPTY = ('postgres_user', 'postgres_password', 'postgres_host', 'postgres_db', 'redis_host')
PORTS = ('postgres_port', 'redis_port')
SECONDS_UP_TO_MINUTE = (
    'redis_timeout_seconds',
    'library_timeout_seconds',
    'library_retry_base_delay_seconds',
    'library_retry_max_delay_seconds',
)
SECONDS_UP_TO_DAY = (
    'cache_invalidation_retry_seconds',
    'cache_invalidation_lease_seconds',
    'library_breaker_reset_seconds',
    'membership_sync_interval_seconds',
    'membership_sync_lease_seconds',
    'membership_sync_retry_base_delay_seconds',
    'membership_sync_retry_max_delay_seconds',
)
BATCH_LIMITS = ('cache_invalidation_batch_size', 'membership_sync_pass_limit')

INVALID_VALUES = [
    *[(name, '') for name in NON_EMPTY],
    *[(name, value) for name in PORTS for value in ('0', '65536', 'x')],
    *[
        (name, value)
        for name in SECONDS_UP_TO_MINUTE
        for value in ('0', '-1', '60.5', 'inf', 'nan', 'x')
    ],
    *[
        (name, value)
        for name in SECONDS_UP_TO_DAY
        for value in ('0', '-1', '86400.5', 'inf', 'nan', 'x')
    ],
    *[(name, value) for name in BATCH_LIMITS for value in ('0', '1001', 'x')],
    ('redis_retries', '-1'),
    ('redis_retries', '11'),
    ('cache_ttl_seconds', '0'),
    ('cache_ttl_seconds', '86401'),
    ('cache_tombstone_ttl_ms', '0'),
    ('cache_tombstone_ttl_ms', '86400001'),
    ('library_url', 'not-a-url'),
    ('library_url', 'ftp://localhost/v1'),
    ('library_retry_attempts', '0'),
    ('library_retry_attempts', '11'),
    ('library_breaker_failure_threshold', '0'),
    ('library_breaker_failure_threshold', '101'),
]

LOWER_BOUNDS: dict[str, object] = {
    'postgres_user': 'a',
    'postgres_password': 'a',
    'postgres_host': 'a',
    'postgres_port': 1,
    'postgres_db': 'a',
    'redis_host': 'a',
    'redis_port': 1,
    'redis_timeout_seconds': 0.001,
    'redis_retries': 0,
    'cache_ttl_seconds': 1,
    'cache_tombstone_ttl_ms': 1,
    'cache_invalidation_retry_seconds': 0.001,
    'cache_invalidation_batch_size': 1,
    'cache_invalidation_lease_seconds': 0.001,
    'library_timeout_seconds': 0.001,
    'library_retry_attempts': 1,
    'library_retry_base_delay_seconds': 0.001,
    'library_retry_max_delay_seconds': 0.001,
    'library_breaker_failure_threshold': 1,
    'library_breaker_reset_seconds': 0.001,
    'membership_sync_interval_seconds': 0.001,
    'membership_sync_pass_limit': 1,
    'membership_sync_lease_seconds': 0.002,
    'membership_sync_retry_base_delay_seconds': 0.001,
    'membership_sync_retry_max_delay_seconds': 0.001,
}

UPPER_BOUNDS: dict[str, object] = {
    'postgres_port': 65535,
    'redis_port': 65535,
    'redis_timeout_seconds': 60,
    'redis_retries': 10,
    'cache_ttl_seconds': 86400,
    'cache_tombstone_ttl_ms': 86_400_000,
    'cache_invalidation_retry_seconds': 86400,
    'cache_invalidation_batch_size': 1000,
    'cache_invalidation_lease_seconds': 86400,
    'library_timeout_seconds': 60,
    'library_retry_attempts': 10,
    'library_retry_base_delay_seconds': 60,
    'library_retry_max_delay_seconds': 60,
    'library_breaker_failure_threshold': 100,
    'library_breaker_reset_seconds': 86400,
    'membership_sync_interval_seconds': 86400,
    'membership_sync_pass_limit': 1000,
    'membership_sync_lease_seconds': 86400,
    'membership_sync_retry_base_delay_seconds': 86400,
    'membership_sync_retry_max_delay_seconds': 86400,
}

LIBRARY_CALL_ENV = {
    'library_retry_attempts': '3',
    'library_timeout_seconds': '2',
    'library_retry_max_delay_seconds': '1',
}
LIBRARY_CALL_SECONDS = 8


@pytest.fixture
def load_settings(monkeypatch: pytest.MonkeyPatch) -> LoadSettings:
    def load(**overrides: str) -> Settings:
        for name, value in {**BASE_ENV, **overrides}.items():
            monkeypatch.setenv(name, value)
        return Settings(_env_file=None)  # type: ignore[call-arg]

    return load


def test_env_file_passes_validation() -> None:
    Settings()  # type: ignore[call-arg]


def test_base_env_covers_every_setting() -> None:
    assert set(BASE_ENV) == set(Settings.model_fields)


def test_every_setting_has_invalid_values() -> None:
    assert {name for name, _ in INVALID_VALUES} == set(Settings.model_fields)


@pytest.mark.parametrize(('name', 'value'), INVALID_VALUES)
def test_invalid_value_is_rejected(load_settings: LoadSettings, name: str, value: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        load_settings(**{name: value})

    assert {error['loc'] for error in exc_info.value.errors()} == {(name,)}


@pytest.mark.parametrize('bounds', [LOWER_BOUNDS, UPPER_BOUNDS], ids=['lower', 'upper'])
def test_boundary_values_are_accepted(
    load_settings: LoadSettings, bounds: dict[str, object]
) -> None:
    settings = load_settings(**{name: str(value) for name, value in bounds.items()})

    assert settings.model_dump(include=set(bounds)) == bounds


@pytest.mark.parametrize('prefix', ['library_retry', 'membership_sync_retry'])
def test_max_delay_below_base_delay_is_rejected(load_settings: LoadSettings, prefix: str) -> None:
    with pytest.raises(ValidationError, match=f'{prefix}_max_delay_seconds must not be less'):
        load_settings(**{f'{prefix}_base_delay_seconds': '2', f'{prefix}_max_delay_seconds': '1.5'})


def test_lease_not_longer_than_library_call_is_rejected(load_settings: LoadSettings) -> None:
    with pytest.raises(ValidationError, match='membership_sync_lease_seconds must exceed'):
        load_settings(**LIBRARY_CALL_ENV, membership_sync_lease_seconds=str(LIBRARY_CALL_SECONDS))


def test_lease_longer_than_library_call_is_accepted(load_settings: LoadSettings) -> None:
    lease = LIBRARY_CALL_SECONDS + 0.5

    settings = load_settings(**LIBRARY_CALL_ENV, membership_sync_lease_seconds=str(lease))

    assert settings.membership_sync_lease_seconds == lease
