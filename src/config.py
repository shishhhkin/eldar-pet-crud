from pathlib import Path

from pydantic import Field, HttpUrl, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / '.env'


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    postgres_db: str

    redis_host: str
    redis_port: int
    redis_timeout_seconds: float
    redis_retries: int

    cache_ttl_seconds: int
    cache_tombstone_ttl_ms: int
    cache_invalidation_retry_seconds: float = Field(gt=0)
    cache_invalidation_batch_size: int = Field(ge=1)
    cache_invalidation_lease_seconds: float = Field(gt=0)

    library_url: HttpUrl
    library_timeout_seconds: float = Field(gt=0)
    library_retry_attempts: int = Field(ge=1)
    library_retry_base_delay_seconds: float = Field(gt=0)
    library_retry_max_delay_seconds: float = Field(gt=0)
    library_breaker_failure_threshold: int = Field(ge=1)
    library_breaker_reset_seconds: float = Field(gt=0)
    membership_sync_interval_seconds: float = Field(gt=0)
    membership_sync_batch_size: int = Field(ge=1)

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
