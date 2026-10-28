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

    # --- Agente instructor de uso (Caty) ---------------------------------- #
    # Sin clave, Caty no existe: el widget no se renderiza y los endpoints
    # devuelven 503. La aplicación funciona igual, que es lo que tiene que pasar
    # en desarrollo y en un arranque en frío.
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    agente_timeout: float = 30.0
    # Para una respuesta que llega por partes, el timeout de lectura es de
    # **inactividad**, no total: cada fragmento que llega lo reinicia. 30 segundos
    # de silencio mataban consultas que estaban funcionando —pasó en la
    # evaluación, una de 79— porque DeepSeek tardó en mandar el primer fragmento.
    # Con 90 segundos, un silencio así ya significa una conexión muerta.
    agente_timeout_lectura: float = 90.0
    agente_timeout_conexion: float = 10.0
    agente_max_entrada: int = 1000
    agente_max_turnos: int = 10
    agente_max_respuesta: int = 2500
    agente_consultas_por_minuto: int = 20
    agente_consultas_por_dia: int = 300

    @property
    def agente_habilitado(self) -> bool:
        return bool(self.deepseek_api_key.strip())

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
