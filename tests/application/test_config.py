import pytest
from pydantic import ValidationError

from src.config import Settings


def test_invalidation_attempts_below_one_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_attempts', '0')

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_single_invalidation_attempt_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_attempts', '1')

    assert Settings().cache_invalidation_attempts == 1  # type: ignore[call-arg]


def test_invalidation_queue_size_below_one_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_queue_size', '0')

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_invalidation_retry_interval_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('cache_invalidation_retry_seconds', '0')

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]
