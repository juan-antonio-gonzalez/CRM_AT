from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Industrial BI Dashboard"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    database_url: str = "sqlite:///./industrial_bi.db"
    cors_origins: list[str] = ["*"]

    log_level: str = "INFO"
    log_json: bool = False

    session_expire_hours: int = 24
    csrf_enabled: bool = True

    @property
    def database_url_resolved(self) -> str:
        return self.database_url


settings = Settings()
