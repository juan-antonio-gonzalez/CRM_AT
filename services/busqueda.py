"""Búsqueda transversal.

Para encontrar "Cartocor" había que entrar a clientes, después a visitas, después a
minutas. Esta búsqueda cruza las cuatro entidades y devuelve todo junto, agrupado y
con enlace a cada registro.

Devuelve resultados acotados por grupo: no es un listado, es un punto de partida. Si
hay más coincidencias de las que se muestran, cada grupo trae el enlace al listado
filtrado correspondiente para verlas todas.
"""

import models

# Cuántos resultados por grupo. Más que esto no ayuda a decidir a dónde ir.
LIMITE = 8


def _texto(valor) -> str:
    return "" if valor is None else str(valor)


def _buscar_clientes(db, q):
    patron = f"%{q}%"
    filas = (
        db.query(models.Customer)
        .filter(models.Customer.is_active.is_(True))
        .filter(
            models.Customer.name.ilike(patron)
            | models.Customer.plant.ilike(patron)
            | models.Customer.city.ilike(patron)
            | models.Customer.industry_sector.ilike(patron)
            | models.Customer.technical_advisor.ilike(patron)
        )
        .order_by(models.Customer.name)
        .limit(LIMITE)
        .all()
    )
    return [{
        "titulo": c.name,
        "detalle": " · ".join(x for x in (c.plant, c.city, c.industry_sector) if x),
        "enlace": f"/clientes?q={q}",
        "icono": "group",
    } for c in filas]


def _buscar_visitas(db, q):
    """Las visitas guardan casi todo en form_data, así que se busca ahí."""
    patron = f"%{q}%"
    campos = ("cliente_nombre", "at", "objetivo")
    condiciones = []
    for campo in campos:
        condiciones.append(
            models.TechnicalVisit2.form_data[campo].as_string().ilike(patron))
    filas = (
        db.query(models.TechnicalVisit2)
        .filter(models.TechnicalVisit2.is_active.is_(True))
        .filter(condiciones[0] | condiciones[1] | condiciones[2])
        .order_by(models.TechnicalVisit2.fecha.desc())
        .limit(LIMITE)
        .all()
    )
    return [{
        "titulo": f"Visita del {v.fecha or 'sin fecha'}",
        "detalle": " · ".join(x for x in (
            (v.form_data or {}).get("cliente_nombre", ""),
            (v.form_data or {}).get("objetivo", ""),
            v.status,
        ) if x),
        "enlace": f"/visitas2/{v.id}/editar",
        "icono": "assignment",
    } for v in filas]


def _buscar_maquinas(db, q):
    patron = f"%{q}%"
    filas = (
        db.query(models.Machine)
        .filter(models.Machine.is_active.is_(True))
        .filter(
            models.Machine.brand.ilike(patron)
            | models.Machine.model.ilike(patron)
            | models.Machine.serial_number.ilike(patron)
            | models.Machine.line.ilike(patron)
            | models.Machine.machine_type.ilike(patron)
        )
        .order_by(models.Machine.brand, models.Machine.model)
        .limit(LIMITE)
        .all()
    )
    return [{
        "titulo": " ".join(x for x in (m.brand, m.model) if x) or "Máquina",
        "detalle": " · ".join(x for x in (
            m.serial_number, m.machine_type, m.plant_assigned, m.status) if x),
        "enlace": f"/maquinaria?q={q}",
        "icono": "precision_manufacturing",
    } for m in filas]


def _buscar_minutas(db, q):
    patron = f"%{q}%"
    campos = ("objetivo", "tipoReunion", "redactor", "lugar")
    condiciones = [
        models.MeetingMinutes.form_data[campo].as_string().ilike(patron)
        for campo in campos
    ]
    filas = (
        db.query(models.MeetingMinutes)
        .filter(models.MeetingMinutes.is_active.is_(True))
        .filter(condiciones[0] | condiciones[1] | condiciones[2] | condiciones[3])
        .order_by(models.MeetingMinutes.fecha.desc())
        .limit(LIMITE)
        .all()
    )
    return [{
        "titulo": (m.form_data or {}).get("objetivo") or f"Minuta del {m.fecha or '?'}",
        "detalle": " · ".join(x for x in (
            m.fecha,
            (m.form_data or {}).get("tipoReunion", ""),
            m.status,
        ) if x),
        "enlace": f"/minutas?q={q}",
        "icono": "description",
    } for m in filas]


# El último campo es el módulo al que pertenece el grupo: sin él, la búsqueda
# mostraba minutas a quien no tiene Minutas, y el enlace lo mandaba a un 403.
GRUPOS = [
    ("clientes", "Clientes", _buscar_clientes, "/clientes?q={q}", "clientes"),
    ("visitas", "Visitas técnicas", _buscar_visitas, "/visitas2?q={q}", "visitas2"),
    ("maquinas", "Máquinas", _buscar_maquinas, "/maquinaria?q={q}", "maquinaria"),
    ("minutas", "Minutas", _buscar_minutas, "/minutas?q={q}", "minutas"),
]


def buscar(db, q: str, modulos=None):
    """Busca en las cuatro entidades. Devuelve (grupos, total).

    `modulos` es lo que ve el usuario. Con `None` no se filtra, para los llamados
    que no vienen de una sesión.
    """
    q = (q or "").strip()
    if len(q) < 2:
        # Con una sola letra cualquier cosa coincide y el resultado no ayuda.
        return [], 0

    grupos = []
    total = 0
    for clave, titulo, funcion, plantilla_enlace, modulo in GRUPOS:
        if modulos is not None and modulo not in modulos:
            continue
        try:
            resultados = funcion(db, q)
        except Exception:
            # Una búsqueda que falla en una entidad no debe tumbar las otras tres.
            resultados = []
        if resultados:
            total += len(resultados)
            grupos.append({
                "clave": clave,
                "titulo": titulo,
                "resultados": resultados,
                "enlace_todos": plantilla_enlace.format(q=q),
                # Puede haber más de los que se muestran.
                "puede_haber_mas": len(resultados) == LIMITE,
            })
    return grupos, total
