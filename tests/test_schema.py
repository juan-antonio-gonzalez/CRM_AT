"""Pruebas de integridad del esquema.

Existen porque el proyecto estuvo mucho tiempo con migraciones que no construían
un esquema ejecutable: ``alembic upgrade head`` producía una base sin las
columnas de soft-delete de 23 tablas, y ``Base.metadata.create_all()`` en el
arranque lo ocultaba. Cualquiera de estas pruebas lo habría detectado.

Corren contra PostgreSQL, que es el único motor soportado. El esquema se
construye con la cadena de migraciones (ver ``conftest.py``), así que estas
pruebas comparan lo que produce Alembic contra lo que declaran los modelos.
"""

import os
import subprocess
import sys

from sqlalchemy import inspect, text

import models  # noqa: F401  (registra las tablas en Base.metadata)
from database import Base

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    """Ejecutar alembic contra la base de pruebas."""
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_models_metadata_is_populated():
    """Importar los modelos debe registrar todas las tablas en Base.metadata.

    Bastantes cosas dependen de esto en silencio; la propia suite llegó a correr
    create_all() sobre una metadata vacía y no creaba ninguna tabla.
    """
    assert len(Base.metadata.tables) >= 28
    for esperada in ("users", "customers", "machines", "products", "trash_items",
                     "at_assignments", "action_plan_tracking", "meeting_minutes"):
        assert esperada in Base.metadata.tables, f"falta la tabla {esperada} en metadata"


def test_engine_is_postgresql(test_engine):
    """El único motor soportado es PostgreSQL."""
    assert test_engine.dialect.name == "postgresql", (
        f"las pruebas deben correr contra PostgreSQL, no {test_engine.dialect.name}"
    )


def test_migrations_produce_the_model_schema(test_engine):
    """``alembic upgrade head`` debe producir exactamente el esquema de los modelos.

    Esta es la prueba de regresión de la deriva de esquema.
    """
    insp = inspect(test_engine)

    migradas = set(insp.get_table_names()) - {"alembic_version"}
    modeladas = set(Base.metadata.tables)

    assert migradas == modeladas, (
        f"tablas solo en migraciones: {sorted(migradas - modeladas)}; "
        f"tablas solo en modelos: {sorted(modeladas - migradas)}"
    )

    faltantes = []
    for tabla in sorted(modeladas):
        columnas_migradas = {c["name"] for c in insp.get_columns(tabla)}
        columnas_modelo = {c.name for c in Base.metadata.tables[tabla].columns}
        ausentes = columnas_modelo - columnas_migradas
        if ausentes:
            faltantes.append((tabla, sorted(ausentes)))

    assert not faltantes, (
        f"columnas declaradas en los modelos y ausentes tras migrar: {faltantes}"
    )


def test_soft_delete_columns_exist_after_migration(test_engine):
    """La familia de columnas de soft-delete debe existir donde se usa."""
    insp = inspect(test_engine)
    tablas = set(insp.get_table_names())

    for tabla in ("customers", "products", "machines", "at_assignments",
                  "action_plan_tracking", "technical_visits_2", "technical_surveys_2"):
        assert tabla in tablas, f"falta la tabla {tabla}"
        columnas = {c["name"] for c in insp.get_columns(tabla)}
        for columna in ("is_active", "inactivation_reason",
                        "inactivated_by_id", "inactivated_at"):
            assert columna in columnas, f"{tabla}.{columna} ausente tras migrar"


def test_at_assignments_customer_name_is_not_unique(test_engine):
    """at_assignments guarda versiones por cliente: el índice no debe ser único."""
    insp = inspect(test_engine)
    for indice in insp.get_indexes("at_assignments"):
        if (indice.get("column_names") or []) == ["customer_name"]:
            assert not indice.get("unique"), (
                "ix_at_assignments_customer_name no debe ser único: la aplicación "
                "guarda una fila por versión y por cliente"
            )


def test_foreign_keys_are_declared(test_engine):
    """Las claves foráneas declaradas en los modelos deben existir en la base.

    PostgreSQL las aplica siempre, a diferencia de SQLite, donde quedaban
    desactivadas y permitían guardar filas huérfanas.
    """
    insp = inspect(test_engine)

    esperadas = {
        "machines": {"customers"},
        "technical_surveys": {"machines"},
        "technical_surveys_2": {"customers", "machines"},
        "infrastructure_surveys": {"customers"},
    }

    for tabla, destinos in esperadas.items():
        reales = {
            fk["referred_table"]
            for fk in insp.get_foreign_keys(tabla)
            if fk.get("referred_table")
        }
        assert destinos <= reales, (
            f"{tabla} debería referenciar {sorted(destinos)} y referencia {sorted(reales)}"
        )


def test_alembic_reports_a_single_head():
    """La cadena de migraciones no debe tener ramas ni múltiples cabezas."""
    resultado = _run_alembic("heads")
    assert resultado.returncode == 0, resultado.stderr
    cabezas = [linea for linea in resultado.stdout.splitlines() if linea.strip()]
    assert len(cabezas) == 1, f"se esperaba una sola cabeza de migraciones: {cabezas}"


def test_models_and_migrations_are_in_sync_for_autogenerate():
    """Un autogenerate no debería detectar cambios pendientes.

    Sirve como red de seguridad: si alguien modifica un modelo y olvida la
    migración, esto lo detecta.
    """
    resultado = _run_alembic("check")
    assert resultado.returncode == 0, (
        "hay diferencias entre los modelos y las migraciones:\n"
        f"{resultado.stdout}\n{resultado.stderr}\n"
        "Generá la migración faltante con: alembic revision --autogenerate"
    )
