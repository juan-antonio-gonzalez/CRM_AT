"""Ayudantes compartidos por los tests.

Existe por un cambio concreto: un cliente se asigna a un **equipo**, y el alta no
acepta los tres nombres sueltos. Los ayudantes de alta de clientes viven en
funciones de módulo que no reciben `db_session`, así que este archivo les da una
forma de conseguir un equipo sin tener que enhebrar la fixture por veinte
llamadas.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Los tres miembros del equipo que usan los tests. Separados y no
# necesariamente iguales a los que cada test escribía antes, porque a partir de
# ahora los nombres del cliente salen del equipo.
COMERCIAL = "COMERCIAL UNO"
DISENADOR = "DISENADOR UNO"
AT = "ING. GOMEZ"

_engine = None


def _engine_de_ayudantes():
    """Una conexión propia contra la base de pruebas.

    `conftest.py` deja `DATABASE_URL` apuntando a la base de pruebas al
    importarse, así que leerla acá siempre da la base correcta.
    """
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    return _engine


def equipo_de_prueba_id() -> int:
    """El id de un equipo con los tres miembros, creándolo si hace falta.

    Es idempotente a propósito: `_clean_tables` vacía las tablas después de cada
    prueba, así que el equipo desaparece entre una y otra y hay que poder
    volver a crearlo. Buscar-o-crear cubre los dos casos con la misma llamada.
    """
    from services import team_service

    Sesion = sessionmaker(bind=_engine_de_ayudantes())
    db = Sesion()
    try:
        equipo = team_service.obtener_o_crear(db, COMERCIAL, DISENADOR, AT)
        db.commit()
        return equipo.id
    finally:
        db.close()
