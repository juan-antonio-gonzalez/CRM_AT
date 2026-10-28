"""Configuración de pytest.

Dos decisiones importantes viven acá:

1. **La URL de la base de pruebas se fuerza antes de importar cualquier módulo
   del proyecto.** ``database.py`` construye el engine al importarse, así que
   parchear ``settings.database_url`` desde un fixture llegaba tarde: el engine
   ya estaba apuntando a la base real y correr las pruebas escribía en ella.

2. **Sólo se soporta PostgreSQL.** Se toma ``DATABASE_URL`` del entorno y se
   apunta a una base cuyo nombre termina en ``_test``, que se reconstruye con
   ``alembic upgrade head``. Así las pruebas ejercitan exactamente el motor y el
   esquema que corren en el servidor.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not os.environ.get("DATABASE_URL"):
    # Un valor por defecto cómodo para desarrollo local. La comprobación de
    # abajo garantiza que nunca se use una base que no sea de pruebas.
    os.environ["DATABASE_URL"] = "postgresql://crm_at:crm_at@127.0.0.1:5432/crm_at_test"


def _pg_test_url(url: str) -> str:
    """Apuntar una URL de PostgreSQL a una base dedicada de pruebas."""
    base, _, query = url.partition("?")
    head, sep, dbname = base.rpartition("/")
    if not sep or not dbname:
        return url
    test_db = dbname if dbname.endswith("_test") else f"{dbname}_test"
    return f"{head}/{test_db}" + (f"?{query}" if query else "")


TEST_DATABASE_URL = _pg_test_url(os.environ["DATABASE_URL"])
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Red de seguridad: los fixtures borran todas las tablas, así que jamás deben
# apuntar a una base real.
if "_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        "Por seguridad, el nombre de la base de pruebas debe terminar en '_test'. "
        f"Recibido: {TEST_DATABASE_URL}"
    )
if TEST_DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "SQLite ya no está soportado. Las pruebas corren contra PostgreSQL. "
        f"Recibido: {TEST_DATABASE_URL}"
    )

os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database import Base, get_db  # noqa: E402
import models  # noqa: E402,F401  (registra todas las tablas en Base.metadata)


def _make_engine():
    return create_engine(TEST_DATABASE_URL, pool_pre_ping=True)


def _apply_migrations() -> None:
    """Correr ``alembic upgrade head`` sobre una base de pruebas limpia."""
    import subprocess

    # Empezar con el esquema vacío para que la cadena de migraciones corra
    # realmente desde cero.
    engine = _make_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DATABASE_URL
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head falló en la base de pruebas:\n"
            f"{result.stdout}\n{result.stderr}"
        )


@pytest.fixture(scope="session")
def test_engine():
    """El engine de la base de pruebas.

    El esquema se construye **corriendo las migraciones**, no con
    ``create_all``: eso es lo que detecta la deriva entre la cadena de
    migraciones y los modelos.
    """
    engine = _make_engine()
    _apply_migrations()
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_module(test_engine):
    """Importar la aplicación recién después de que exista el engine de pruebas."""
    import main
    return main


@pytest.fixture
def db_session(test_engine):
    """Una sesión para preparar datos y hacer aserciones directamente."""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _clean_tables(test_engine):
    """Empezar cada prueba con las tablas vacías.

    ``TRUNCATE ... RESTART IDENTITY CASCADE`` limpia todo de una pasada y
    reinicia las secuencias, así que los ids son predecibles en cada prueba.
    """
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with test_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(app_module, test_engine):
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(app_module.app) as c:
        yield c
    app_module.app.dependency_overrides.clear()


@pytest.fixture
def seed_admin(db_session):
    from security import hash_password
    import models

    existing = db_session.query(models.User).filter(models.User.username == "admin").first()
    if not existing:
        existing = models.User(
            username="admin",
            email="admin@crm-at.com",
            hashed_password=hash_password("admin123"),
            full_name="Administrador",
            role="admin",
            is_active=True,
        )
        db_session.add(existing)
        db_session.commit()
    # Se devuelve el usuario de verdad: antes devolvía `existing`, que en la
    # primera corrida era `None` y hacía fallar a quien pidiera esta fixture.
    return db_session.query(models.User).filter(models.User.username == "admin").one()


@pytest.fixture
def admin_cookie(client, db_session, seed_admin):
    """Iniciar sesión como admin y devolver la cookie de sesión."""
    from enums import CustomerStatus, ProductStatus
    import models

    if db_session.query(models.Customer).count() == 0:
        db_session.add_all([
            models.Customer(name="Steel Metrics S.A.", plant="Planta Monterrey",
                            industry_sector="Metalurgia", assigned_commercial="Carlos Pérez",
                            city="Monterrey", status=CustomerStatus.CLIENTE.value, is_active=True),
            models.Customer(name="AutoVanguard Corp.", plant="Sede Querétaro",
                            industry_sector="Automotriz", assigned_commercial="Elena Rodríguez",
                            city="Querétaro", status=CustomerStatus.CLIENTE.value, is_active=True),
        ])
    if db_session.query(models.Product).count() == 0:
        db_session.add(models.Product(name="Test Product 1", et_number="ET-001",
                                      material="Corrugado Simple",
                                      status=ProductStatus.ACTIVO.value, is_active=True))
    db_session.commit()

    r = client.post("/auth/login", data={"username": "admin", "password": "admin123"},
                    follow_redirects=False)
    assert r.status_code == 303, f"login falló: {r.status_code} {r.text[:200]}"
    return r.headers.get("set-cookie", "").split(";")[0]
