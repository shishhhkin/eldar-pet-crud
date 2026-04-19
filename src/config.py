# --- Устаревший вариант (pydantic v1 стиль внутри pydantic-settings v2) ---
# import os
#
# from pydantic import PostgresDsn, Field
# from pydantic_settings import BaseSettings
#
#
# class Settings(BaseSettings):
#     postgres_url: PostgresDsn = Field(env='postgres_url')
#     # Параметр `env=` в Field удалён в pydantic v2.
#     # Вложенный `class Config` заменён на `model_config = SettingsConfigDict(...)`.
#
#     class Config:
#         env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
# --------------------------------------------------------------------------

# Актуальный подход: pydantic v2 + pydantic-settings v2.
# - `model_config = SettingsConfigDict(...)` вместо вложенного class Config
# - pathlib.Path вместо os.path.join/dirname
# - имя переменной окружения определяется по имени поля (case_insensitive),
#   а если нужен явный alias — используется validation_alias, а не удалённый env=.
from pathlib import Path

from pydantic import PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / '.env'


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    postgres_db: str

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
