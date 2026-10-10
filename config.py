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

    # PostgreSQL es el único motor soportado: es el que corre en el servidor, y
    # mantener un segundo motor (SQLite) en desarrollo hacía que los errores que
    # ese motor permisivo ocultaba aparecieran recién en producción.
    database_url: str = "postgresql://crm_at:crm_at@127.0.0.1:5432/crm_at"
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

        ``postgres://`` is what some providers hand out, but SQLAlchemy only
        understands ``postgresql://``. A query string such as
        ``?sslmode=require`` is preserved.
        """
        url = (self.database_url or "").strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url


settings = Settings()
