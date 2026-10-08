from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, HttpUrl, PostgresDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / '.env'

NonEmptyStr = Annotated[str, Field(min_length=1)]
Port = Annotated[int, Field(ge=1, le=65535)]
BatchLimit = Annotated[int, Field(ge=1, le=1000)]
SecondsUpToMinute = Annotated[float, Field(gt=0, le=60)]
SecondsUpToDay = Annotated[float, Field(gt=0, le=86400)]


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
    membership_sync_retry_base_delay_seconds: SecondsUpToDay
    membership_sync_retry_max_delay_seconds: SecondsUpToDay

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

    @model_validator(mode='after')
    def _check_consistency(self) -> Self:
        retry_delays = {
            'library_retry': (
                self.library_retry_base_delay_seconds,
                self.library_retry_max_delay_seconds,
            ),
            'membership_sync_retry': (
                self.membership_sync_retry_base_delay_seconds,
                self.membership_sync_retry_max_delay_seconds,
            ),
        }
        for prefix, (base, cap) in retry_delays.items():
            if cap < base:
                raise ValueError(
                    f'{prefix}_max_delay_seconds must not be less than {prefix}_base_delay_seconds'
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
        return self
