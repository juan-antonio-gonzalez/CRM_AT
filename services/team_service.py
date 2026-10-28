"""Equipos: comercial, diseñador y AT como una unidad reutilizable.

Sobre las dos decisiones que se ven en el código
------------------------------------------------
**El equipo no se borra: se desactiva.** No tiene sentido eliminarlo, porque los
clientes que lo tuvieron asignado guardan su `team_id` y la clave foránea lo
impediría igual. Desactivar además conserva el rastro: un cliente viejo sigue
apuntando a un equipo que se entiende por qué ya no se usa.

**Los miembros se validan acá y no sólo en la base.** El `NOT NULL` de las tres
columnas es la garantía final, pero sin esta validación un equipo incompleto
llegaría hasta el `INSERT` y el usuario vería un error 500 en vez de un mensaje.
La base impide el dato; acá se explica.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

import models

MIEMBROS = ("commercial", "designer", "technical_advisor")
ETIQUETAS_MIEMBRO = {
    "commercial": "comercial",
    "designer": "diseñador",
    "technical_advisor": "AT",
}


def _normalizar(valor: str) -> str:
    return (valor or "").strip().upper()


def _validar(nombre: str, comercial: str, disenador: str, at: str) -> dict:
    """Devuelve los cuatro valores normalizados, o explica qué falta."""
    valores = {
        "name": _normalizar(nombre),
        "commercial": _normalizar(comercial),
        "designer": _normalizar(disenador),
        "technical_advisor": _normalizar(at),
    }
    if not valores["name"]:
        raise HTTPException(status_code=400, detail="El equipo necesita un nombre")

    faltan = [ETIQUETAS_MIEMBRO[c] for c in MIEMBROS if not valores[c]]
    if faltan:
        raise HTTPException(
            status_code=400,
            detail="Un equipo no puede estar incompleto. Falta: " + ", ".join(faltan),
        )
    return valores


def listar(db: Session, q: str = "", estado: str = "") -> list[models.Team]:
    consulta = db.query(models.Team)
    if q:
        patron = f"%{q}%"
        consulta = consulta.filter(
            models.Team.name.ilike(patron)
            | models.Team.commercial.ilike(patron)
            | models.Team.designer.ilike(patron)
            | models.Team.technical_advisor.ilike(patron)
        )
    if estado == "activos":
        consulta = consulta.filter(models.Team.is_active.is_(True))
    elif estado == "inactivos":
        consulta = consulta.filter(models.Team.is_active.is_(False))
    return consulta.order_by(models.Team.is_active.desc(), models.Team.name).all()


def obtener(db: Session, team_id: int) -> models.Team:
    equipo = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


def _nombre_tomado(db: Session, nombre: str, excepto_id: int | None = None) -> bool:
    consulta = db.query(models.Team).filter(models.Team.name == nombre)
    if excepto_id is not None:
        consulta = consulta.filter(models.Team.id != excepto_id)
    return db.query(consulta.exists()).scalar()


def crear(db: Session, nombre: str, comercial: str, disenador: str, at: str,
          observaciones: str = "") -> models.Team:
    valores = _validar(nombre, comercial, disenador, at)

    if _nombre_tomado(db, valores["name"]):
        # El índice único es sobre todas las filas, incluidas las desactivadas.
        # Sin este mensaje, el usuario vería un error de base sin entender que el
        # nombre lo tiene un equipo que dio de baja.
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un equipo llamado «{valores['name']}». "
                   f"Si está desactivado, reactivalo en vez de crear otro.",
        )

    equipo = models.Team(
        name=valores["name"],
        commercial=valores["commercial"],
        designer=valores["designer"],
        technical_advisor=valores["technical_advisor"],
        observations=(observaciones or "").strip() or None,
        is_active=True,
    )
    db.add(equipo)
    db.commit()
    db.refresh(equipo)
    return equipo


def actualizar(db: Session, team_id: int, nombre: str, comercial: str,
               disenador: str, at: str, observaciones: str = "") -> models.Team:
    equipo = obtener(db, team_id)
    valores = _validar(nombre, comercial, disenador, at)

    if _nombre_tomado(db, valores["name"], excepto_id=team_id):
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe otro equipo llamado «{valores['name']}».",
        )

    equipo.name = valores["name"]
    equipo.commercial = valores["commercial"]
    equipo.designer = valores["designer"]
    equipo.technical_advisor = valores["technical_advisor"]
    equipo.observations = (observaciones or "").strip() or None
    db.commit()
    db.refresh(equipo)
    return equipo


def clientes_asignados(db: Session, team_id: int) -> int:
    """Cuántas filas de cliente apuntan a este equipo.

    Es la cuenta que se muestra antes de desactivar: un equipo en uso se puede
    desactivar, pero el usuario tiene que saber a cuántos clientes afecta.
    """
    return (
        db.query(func.count(models.Customer.id))
        .filter(models.Customer.team_id == team_id)
        .scalar()
        or 0
    )


def conteo_por_equipo(db: Session) -> dict[int, int]:
    """Cuántos clientes tiene cada equipo, en una sola consulta.

    Se resuelve con un `GROUP BY` y no llamando a `clientes_asignados` por fila:
    con veinte equipos serían veintiuna consultas para pintar un listado.
    """
    filas = (
        db.query(models.Customer.team_id, func.count(models.Customer.id))
        .filter(models.Customer.team_id.isnot(None))
        .group_by(models.Customer.team_id)
        .all()
    )
    return {team_id: total for team_id, total in filas}


def equipos_repetidos(db: Session) -> set[int]:
    """Ids de equipos activos que comparten los tres miembros con otro.

    No se impide: dos equipos con las mismas personas pueden tener sentido por
    zona o por turno. Pero conviene que se vea, porque lo más probable es que sea
    uno creado dos veces con otro nombre.
    """
    combinaciones: dict[tuple, list[int]] = {}
    for equipo in db.query(models.Team).filter(models.Team.is_active.is_(True)).all():
        clave = (equipo.commercial, equipo.designer, equipo.technical_advisor)
        combinaciones.setdefault(clave, []).append(equipo.id)

    repetidos: set[int] = set()
    for ids in combinaciones.values():
        if len(ids) > 1:
            repetidos.update(ids)
    return repetidos


def obtener_o_crear(db: Session, comercial: str, disenador: str, at: str):
    """El equipo activo con esos tres miembros, creándolo si no existe.

    Lo usa la importación de Excel: una planilla que trae las tres personas no
    puede dejar al cliente sin equipo, porque a partir de ahora el equipo es la
    unidad que se asigna. Si el equipo no existe se crea, con los tres nombres
    como nombre provisorio para que se lo pueda encontrar y renombrar después.

    **Devuelve `None` si falta alguno de los tres.** No se arma un equipo a
    medias: la regla es que un equipo no puede estar incompleto, y una planilla
    incompleta no es motivo para romperla.
    """
    comercial = _normalizar(comercial)
    disenador = _normalizar(disenador)
    at = _normalizar(at)
    if not (comercial and disenador and at):
        return None

    existente = (
        db.query(models.Team)
        .filter(models.Team.commercial == comercial,
                models.Team.designer == disenador,
                models.Team.technical_advisor == at,
                models.Team.is_active.is_(True))
        .first()
    )
    if existente:
        return existente

    base = f"{comercial} / {disenador} / {at}"
    nombre, sufijo = base, 1
    while _nombre_tomado(db, nombre):
        sufijo += 1
        nombre = f"{base} ({sufijo})"

    equipo = models.Team(name=nombre, commercial=comercial, designer=disenador,
                         technical_advisor=at, is_active=True)
    db.add(equipo)
    db.flush()
    return equipo


def clientes_del_equipo(db: Session, team_id: int) -> list:
    """Las filas de cliente activas que tienen este equipo asignado."""
    return (
        db.query(models.Customer)
        .filter(models.Customer.team_id == team_id,
                models.Customer.is_active.is_(True))
        .order_by(models.Customer.name, models.Customer.plant)
        .all()
    )


def actualizar_asignaciones(db: Session, team_id: int) -> dict:
    """Reaplica los tres miembros del equipo a todos los clientes que lo tienen.

    Es la acción explícita del caso contrario al diseño. Asignar guarda una **foto**
    del momento, así que editar un equipo no reescribe a sus clientes: un informe de
    marzo tiene que seguir diciendo quién estaba en marzo. Cuando lo que se quiere
    es justamente lo otro —corregir el equipo y que todos sus clientes lo reflejen—
    se corre esto, que antes dice a cuántos afecta.

    También mueve la asignación AT vigente de cada planta: si el cliente dijera un
    AT y el control de asignaciones otro, el sistema tendría dos verdades.
    """
    equipo = obtener(db, team_id)
    clientes = clientes_del_equipo(db, team_id)
    asignaciones = 0

    for cliente in clientes:
        cliente.assigned_commercial = equipo.commercial
        cliente.designer = equipo.designer
        cliente.technical_advisor = equipo.technical_advisor

        filtros = [
            models.ATAssignment.customer_name == cliente.name,
            models.ATAssignment.valid_to.is_(None),
            # El `IS NULL` cubre una asignación de antes de que existiera la
            # columna: ésas eran por cliente, así que hay a lo sumo una.
            or_(models.ATAssignment.plant == cliente.plant,
                models.ATAssignment.plant.is_(None)),
        ]
        asignaciones += (
            db.query(models.ATAssignment)
            .filter(*filtros)
            .update({"technical_advisor": equipo.technical_advisor},
                    synchronize_session=False)
        )

    db.commit()
    return {"clientes": len(clientes), "asignaciones": asignaciones}


def aplicar_a_todas_las_plantas(db: Session, equipo_id: int, nombre_cliente: str,
                                excepto_id: int) -> int:
    """Aplica el equipo a las demás filas del mismo cliente.

    Un cliente con varias plantas son varias filas con el mismo nombre. Cambiar el
    equipo de una y dejar las otras como estaban es lo correcto por defecto —cada
    planta tiene el suyo—, pero cuando el equipo es del cliente entero hay que
    poder hacerlo de una vez en lugar de repetir la edición por planta.

    Devuelve cuántas filas cambió, sin contar la que se está editando.
    """
    equipo = obtener(db, equipo_id)
    hermanas = (
        db.query(models.Customer)
        .filter(models.Customer.name == nombre_cliente,
                models.Customer.id != excepto_id,
                models.Customer.is_active.is_(True))
        .all()
    )

    for cliente in hermanas:
        cliente.team_id = equipo.id
        cliente.assigned_commercial = equipo.commercial
        cliente.designer = equipo.designer
        cliente.technical_advisor = equipo.technical_advisor

    db.commit()
    return len(hermanas)
