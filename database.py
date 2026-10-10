"""Motor de base de datos, fábrica de sesiones y dependencia de FastAPI.

PostgreSQL es el único motor soportado, tanto en el servidor como en
desarrollo. Antes el proyecto soportaba también SQLite, lo que resultó ser un
problema: el motor permisivo aceptaba en silencio esquemas y datos que
PostgreSQL rechaza, así que toda una clase de errores (columnas faltantes,
claves foráneas sin aplicar, un índice único que la aplicación no podía
cumplir) aparecía recién en producción. Con un solo motor desaparecen las ramas
por dialecto en las migraciones, y las pruebas ejercitan exactamente lo que
corre en el servidor.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

SQLALCHEMY_DATABASE_URL = settings.database_url_resolved

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "SQLite ya no está soportado. Configurá DATABASE_URL apuntando a "
        "PostgreSQL, por ejemplo: "
        "postgresql://usuario:clave@127.0.0.1:5432/crm_at"
    )

# ``pool_pre_ping`` evita que conexiones de larga vida mueran en silencio detrás
# de un NAT o firewall; ``pool_recycle`` evita los cortes por inactividad del
# servidor.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Entrega una sesión y siempre la cierra.

    A propósito no hay ``rollback()`` acá: ``Session.close()`` ya descarta la
    transacción, y hacer rollback antes desacoplaría el estado pendiente, de modo
    que el manejador de ``IntegrityError`` de la aplicación ya no podría leer el
    nombre de la restricción desde la excepción. ``main.py`` maneja esa excepción
    explícitamente y hace el rollback ahí.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
