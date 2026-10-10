"""Schema integrity tests.

These exist because the project shipped for months with migrations that did not
build a runnable schema: ``alembic upgrade head`` produced a database missing 23
tables' worth of soft-delete columns, and ``Base.metadata.create_all()`` at
startup silently hid it. Any of these tests would have caught that.
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

import models
from database import Base

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_alembic_upgrade(db_path: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_models_metadata_is_populated():
    """Importing models must register every table on Base.metadata.

    A surprising number of things silently depend on this; the test suite itself
    previously ran create_all() against an empty metadata and created no tables.
    """
    assert len(Base.metadata.tables) >= 28
    for expected in ("users", "customers", "machines", "products", "trash_items",
                     "at_assignments", "action_plan_tracking", "meeting_minutes"):
        assert expected in Base.metadata.tables, f"falta la tabla {expected} en metadata"


def test_migrations_produce_the_model_schema(tmp_path):
    """`alembic upgrade head` must yield exactly the schema the models declare.

    This is the regression test for the schema drift bug.
    """
    db_path = str(tmp_path / "migrated.db")
    result = _run_alembic_upgrade(db_path)
    assert result.returncode == 0, (
        f"alembic upgrade head falló:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    engine = create_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)

    migrated_tables = set(insp.get_table_names()) - {"alembic_version"}
    model_tables = set(Base.metadata.tables)

    assert migrated_tables == model_tables, (
        f"tablas solo en migraciones: {sorted(migrated_tables - model_tables)}; "
        f"tablas solo en modelos: {sorted(model_tables - migrated_tables)}"
    )

    missing = []
    for table in sorted(model_tables):
        migrated_cols = {c["name"] for c in insp.get_columns(table)}
        model_cols = {c.name for c in Base.metadata.tables[table].columns}
        absent = model_cols - migrated_cols
        if absent:
            missing.append((table, sorted(absent)))

    assert not missing, f"columnas declaradas en modelos y ausentes tras migrar: {missing}"
    engine.dispose()


def test_soft_delete_columns_exist_after_migration(tmp_path):
    """The soft-delete column family must exist on the tables that use it."""
    db_path = str(tmp_path / "softdelete.db")
    assert _run_alembic_upgrade(db_path).returncode == 0

    engine = create_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    for table in ("customers", "products", "machines", "at_assignments",
                  "action_plan_tracking", "technical_visits_2", "technical_surveys_2"):
        assert table in tables, f"falta la tabla {table}"
        cols = {c["name"] for c in insp.get_columns(table)}
        for col in ("is_active", "inactivation_reason", "inactivated_by_id", "inactivated_at"):
            assert col in cols, f"{table}.{col} ausente tras migrate"
    engine.dispose()


def test_at_assignments_customer_name_is_not_unique(tmp_path):
    """at_assignments keeps version rows per customer, so the index must not be unique."""
    db_path = str(tmp_path / "unique.db")
    assert _run_alembic_upgrade(db_path).returncode == 0

    engine = create_engine(f"sqlite:///{db_path}")
    insp = inspect(engine)
    for idx in insp.get_indexes("at_assignments"):
        if (idx.get("column_names") or []) == ["customer_name"]:
            assert not idx.get("unique"), "ix_at_assignments_customer_name no debe ser unique"
    engine.dispose()


def test_foreign_keys_are_enforced_on_sqlite():
    """The application engine must turn PRAGMA foreign_keys ON."""
    from database import engine

    if not str(engine.url).startswith("sqlite"):
        pytest.skip("solo aplica a SQLite")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
