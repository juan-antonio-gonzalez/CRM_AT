"""Pytest configuration.

Important: the test database URL is forced **before** any project module is
imported. ``database.py`` builds the SQLAlchemy engine at import time, so
patching ``settings.database_url`` from a fixture was too late — the engine had
already been bound to the real ``industrial_bi.db``, and running the suite wrote
to the developer's database. Here we set the environment variable first, which
``config.Settings`` picks up when it is first instantiated.

Which database is used:

* If ``DATABASE_URL`` is **not** set, tests run on a throwaway SQLite file.
* If ``DATABASE_URL`` **is** set (as CI does for the PostgreSQL job), tests run
  against that server using a ``<name>_test`` database, so the same suite also
  validates PostgreSQL behaviour — where the SQLite-only bugs did not appear.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

USE_SQLITE = not os.environ.get("DATABASE_URL")

if USE_SQLITE:
    # Must happen before importing anything that touches config/database.
    TEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_crm_at.db")
    TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    TEST_DB_PATH = None

    def _pg_test_url(url: str) -> str:
        """Point a postgres URL at a dedicated _test database."""
        base, _, query = url.partition("?")
        head, sep, dbname = base.rpartition("/")
        if not sep or not dbname:
            return url
        test_db = dbname if dbname.endswith("_test") else f"{dbname}_test"
        return f"{head}/{test_db}" + (f"?{query}" if query else "")

    TEST_DATABASE_URL = _pg_test_url(os.environ["DATABASE_URL"])
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Safety net: never point the destructive test fixtures at a real database.
if not (TEST_DATABASE_URL.startswith("sqlite") or "_test" in TEST_DATABASE_URL):
    raise RuntimeError(
        "Por seguridad, la URL de pruebas debe ser SQLite o contener '_test'. "
        f"Recibido: {TEST_DATABASE_URL}"
    )

os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database import Base, get_db  # noqa: E402
import models  # noqa: E402,F401  (registers every table on Base.metadata)


def _make_engine():
    if not USE_SQLITE:
        return create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


@pytest.fixture(scope="session")
def test_engine():
    """The test database engine.

    On PostgreSQL the schema is built by **running the migrations**, not by
    ``create_all``: that is what catches SQLite-only DDL and drift between the
    migration chain and the ORM models on the engine we actually deploy.
    """
    if USE_SQLITE and os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    engine = _make_engine()

    if USE_SQLITE:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        _apply_migrations()

    yield engine
    engine.dispose()
    if USE_SQLITE and TEST_DB_PATH:
        for suffix in ("", "-wal", "-shm"):
            path = TEST_DB_PATH + suffix
            if os.path.exists(path):
                os.remove(path)


def _apply_migrations() -> None:
    """Run alembic upgrade head against a clean test database."""
    import subprocess

    # Start from an empty schema so the migration chain really runs from zero.
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
def app_module(test_engine):
    """Import the app only after the test engine exists."""
    import main
    return main


@pytest.fixture
def db_session(test_engine):
    """A session for direct data setup and assertions."""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _clean_tables(test_engine):
    """Start every test with empty tables.

    Dialect-aware: ``PRAGMA`` is SQLite-only, and the earlier unconditional use
    of it broke every PostgreSQL test at teardown.
    """
    yield
    dialect = test_engine.dialect.name
    with test_engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f'DELETE FROM "{table.name}"'))
            conn.execute(text("PRAGMA foreign_keys=ON"))
        else:
            # PostgreSQL: TRUNCATE ... CASCADE clears everything in one pass and
            # resets the identity sequences so ids stay predictable per test.
            tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
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
        db_session.add(models.User(
            username="admin",
            email="admin@crm-at.com",
            hashed_password=hash_password("admin123"),
            full_name="Administrador",
            role="admin",
            is_active=True,
        ))
        db_session.commit()
    return existing


@pytest.fixture
def admin_cookie(client, db_session, seed_admin):
    """Log in as admin and return the session cookie."""
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
