import re
from pathlib import Path
from typing import Annotated, Self

from pydantic import (
    Field,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / '.env'

NonEmptyStr = Annotated[str, Field(min_length=1)]
Port = Annotated[int, Field(ge=1, le=65535)]
BatchLimit = Annotated[int, Field(ge=1, le=1000)]
SecondsUpToMinute = Annotated[float, Field(gt=0, le=60)]
SecondsUpToDay = Annotated[float, Field(gt=0, le=86400)]
KafkaTopic = Annotated[str, Field(pattern=r'^[A-Za-z0-9._-]{1,249}$')]

_BOOTSTRAP_SERVER_RE = re.compile(r'[^\s,:]+:(\d{1,5})')


class Settings(BaseSettings):
    postgres_user: NonEmptyStr
    postgres_password: NonEmptyStr
    postgres_host: NonEmptyStr
    postgres_port: Port
    postgres_db: NonEmptyStr

    redis_host: NonEmptyStr
    redis_port: Port
    redis_timeout_seconds: SecondsUpToMinute
    redis_retries: int = Field(ge=0, le=10)

    cache_ttl_seconds: int = Field(ge=1, le=86400)
    cache_tombstone_ttl_ms: int = Field(ge=1, le=86_400_000)
    cache_invalidation_retry_seconds: SecondsUpToDay
    cache_invalidation_batch_size: BatchLimit
    cache_invalidation_lease_seconds: SecondsUpToDay

    library_url: HttpUrl
    library_timeout_seconds: SecondsUpToMinute
    library_retry_attempts: int = Field(ge=1, le=10)
    library_retry_base_delay_seconds: SecondsUpToMinute
    library_retry_max_delay_seconds: SecondsUpToMinute
    library_breaker_failure_threshold: int = Field(ge=1, le=100)
    library_breaker_reset_seconds: SecondsUpToDay

    membership_sync_interval_seconds: SecondsUpToDay
    membership_sync_pass_limit: BatchLimit
    membership_sync_lease_seconds: SecondsUpToDay

    kafka_bootstrap_servers: str
    kafka_book_reservations_topic: KafkaTopic
    kafka_send_timeout_seconds: SecondsUpToMinute

    book_reservation_relay_interval_seconds: SecondsUpToDay
    book_reservation_relay_pass_limit: BatchLimit
    book_reservation_relay_lease_seconds: SecondsUpToDay

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_url(self) -> PostgresDsn:
        return PostgresDsn.build(  # type: ignore[return-value]
            scheme='postgresql+asyncpg',
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            path=self.postgres_db,
        )

    @field_validator('kafka_bootstrap_servers')
    @classmethod
    def _check_bootstrap_servers(cls, value: str) -> str:
        for server in value.split(','):
            match = _BOOTSTRAP_SERVER_RE.fullmatch(server)
            if match is None or not 1 <= int(match.group(1)) <= 65535:
                raise ValueError(
                    'kafka_bootstrap_servers must be a comma-separated list of host:port'
                )
        return value

    @model_validator(mode='after')
    def _check_consistency(self) -> Self:
        if self.library_retry_max_delay_seconds < self.library_retry_base_delay_seconds:
            raise ValueError(
                'library_retry_max_delay_seconds must not be less than '
                'library_retry_base_delay_seconds'
            )
        library_call_seconds = (
            self.library_retry_attempts * self.library_timeout_seconds
            + (self.library_retry_attempts - 1) * self.library_retry_max_delay_seconds
        )
        if self.membership_sync_lease_seconds <= library_call_seconds:
            raise ValueError(
                'membership_sync_lease_seconds must exceed the longest library call '
                f'({library_call_seconds:g}s)'
            )
        if self.book_reservation_relay_lease_seconds <= 2 * self.kafka_send_timeout_seconds:
            raise ValueError(
                'book_reservation_relay_lease_seconds must exceed twice kafka_send_timeout_seconds'
            )
        return self
