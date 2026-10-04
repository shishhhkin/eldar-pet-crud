import pytest
from pydantic import ValidationError

from src.config import Settings


def test_invalidation_batch_size_below_one_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_batch_size', '0')

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_single_invalidation_per_batch_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_batch_size', '1')

    assert Settings().cache_invalidation_batch_size == 1  # type: ignore[call-arg]


def test_invalidation_retry_interval_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_retry_seconds', '0')

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_invalidation_lease_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_lease_seconds', '0')

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('library_url', 'not-a-url'),
        ('library_timeout_seconds', '0'),
        ('library_retry_attempts', '0'),
        ('library_retry_base_delay_seconds', '0'),
        ('library_retry_max_delay_seconds', '0'),
        ('library_breaker_failure_threshold', '0'),
        ('library_breaker_reset_seconds', '0'),
        ('membership_sync_interval_seconds', '0'),
        ('membership_sync_batch_size', '0'),
    ],
)
def test_invalid_library_settings_are_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    monkeypatch.setenv(field, value)

    with pytest.raises(ValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    assert [error['loc'] for error in exc_info.value.errors()] == [(field,)]


def test_single_library_attempt_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('library_retry_attempts', '1')

    assert Settings().library_retry_attempts == 1  # type: ignore[call-arg]
