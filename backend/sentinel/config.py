from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from .secrets import decrypt_windows_secret

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_prefix="SENTINEL_", extra="ignore"
    )
    database_url: str = "postgresql+psycopg://sentinel_app@127.0.0.1:55434/api_sentinel_review"
    db_password: str = ""
    db_password_file: str = ""
    allowed_origins: str = "http://127.0.0.1:5175,http://localhost:5175"
    max_services: int = 1000
    monitoring_enabled: bool = True
    check_concurrency: int = Field(default=4, ge=1, le=8)

    def connection_url(self):
        url = make_url(self.database_url)
        if url.drivername.startswith("sqlite"):
            return url
        password = self.db_password
        if not password and self.db_password_file:
            password = decrypt_windows_secret((ROOT / self.db_password_file).resolve())
        return url.set(password=password) if password else url


@lru_cache
def get_settings():
    return Settings()
