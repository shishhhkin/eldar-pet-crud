import os

from pydantic import PostgresDsn, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_url: PostgresDsn = Field(env='postgres_url')

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
