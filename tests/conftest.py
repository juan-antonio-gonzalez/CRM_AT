import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from config import settings


TEST_DATABASE_URL = "sqlite:///./test_industrial_bi.db"


@pytest.fixture(scope="session", autouse=True)
def _setup_env():
    old_debug = settings.debug
    old_db = settings.database_url
    settings.debug = False
    settings.database_url = TEST_DATABASE_URL
    yield
    settings.debug = old_debug
    settings.database_url = old_db


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()
    if os.path.exists("test_industrial_bi.db"):
        os.remove("test_industrial_bi.db")


@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def seed_admin(db_session):
    from security import hash_password
    import models

    existing = db_session.query(models.User).filter(models.User.username == "admin").first()
    if not existing:
        admin = models.User(
            username="admin",
            email="admin@crm-at.com",
            hashed_password=hash_password("admin123"),
            full_name="Administrador",
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()


@pytest.fixture
def admin_cookie(client, db_session, seed_admin):
    from enums import CustomerStatus, ProductStatus
    import models

    if db_session.query(models.Customer).count() == 0:
        db_session.add_all([
            models.Customer(name="Steel Metrics S.A.", plant="Planta Monterrey",
                            industry_sector="Metalurgia", assigned_commercial="Carlos Pérez",
                            city="Monterrey", status=CustomerStatus.CLIENTE.value),
            models.Customer(name="AutoVanguard Corp.", plant="Sede Querétaro",
                            industry_sector="Automotriz", assigned_commercial="Elena Rodríguez",
                            city="Querétaro", status=CustomerStatus.CLIENTE.value),
        ])

    if db_session.query(models.Product).count() == 0:
        db_session.add_all([
            models.Product(name="Test Product 1", et_number="ET-001", material="Corrugado Simple",
                           status=ProductStatus.ACTIVO.value, last_modified="Hoy"),
        ])

    db_session.commit()

    r = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=False)
    assert r.status_code == 303
    return r.headers.get('set-cookie', '').split(';')[0]
