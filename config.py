from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Industrial BI Dashboard"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    database_url: str = "sqlite:///./industrial_bi.db"
    cors_origins: list[str] = ["*"]

    log_level: str = "INFO"
    log_json: bool = False

    session_expire_hours: int = 24
    cookie_secure: bool = False
    csrf_enabled: bool = True

    # Uploaded files live under this directory (served from /static).
    upload_dir: str = "static/uploads"

    @property
    def database_url_resolved(self) -> str:
        """Normalise the database URL.

        ``postgres://`` is what Heroku/Neon/Render hand out, but SQLAlchemy only
        understands ``postgresql://``. Neon also appends ``?sslmode=require``,
        which psycopg2 accepts, so the query string is preserved.
        """
        url = (self.database_url or "").strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.database_url_resolved.startswith("sqlite")


settings = Settings()
