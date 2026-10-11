"""Pruebas del panel de atención del dashboard.

El dashboard describía el estado pero no decía qué hacer. El panel cruza cuatro
condiciones y cada una lleva al listado filtrado. Estas pruebas crean cada
condición y verifican que aparezca, y que no aparezca cuando no corresponde.
"""

import datetime

import models
from enums import RelevamientoStatus, TrackingStatus
from services import dashboard_service


HOY = datetime.datetime(2026, 6, 15, 10, 0, tzinfo=datetime.UTC)


def _cliente(db, nombre="Cliente Prueba", activo=True, **extra):
    c = models.Customer(
        name=nombre,
        is_active=activo,
        status="Activo",
        relevamiento_status=RelevamientoStatus.COMPLETADO.value,
        **extra,
    )
    db.add(c)
    db.commit()
    return c


def _visita(db, cliente, fecha):
    v = models.TechnicalVisit2(
        fecha=fecha,
        status="Finalizado",
        is_active=True,
        form_data={"cliente_nombre": cliente, "at": "ING. PRUEBA"},
    )
    db.add(v)
    db.commit()
    return v


def _maquina(db, cliente_id, estado):
    m = models.Machine(
        customer_id=cliente_id,
        relevamiento_status=estado,
        is_active=True,
        brand="Marca",
        model="Modelo",
    )
    db.add(m)
    db.commit()
    return m


def _minuta(db, fecha, status="Borrador"):
    m = models.MeetingMinutes(
        fecha=fecha,
        status=status,
        is_active=True,
        form_data={"objetivo": "Reunión de prueba"},
    )
    db.add(m)
    db.commit()
    return m


def _tarea(db, vence, status=TrackingStatus.PENDIENTE.value):
    t = models.ActionPlanTracking(
        customer_name="Cliente Prueba",
        task="Tarea de prueba",
        responsible="Alguien",
        due_date=vence,
        status=status,
        is_active=True,
    )
    db.add(t)
    db.commit()
    return t


def _claves(items):
    return {i["clave"] for i in items}


def test_sin_pendientes_el_panel_esta_vacio(db_session):
    """Sin nada pendiente, el panel no aparece: así conserva su fuerza."""
    _cliente(db_session, "Al día")
    _visita(db_session, "Al día", HOY.date().isoformat())
    items = dashboard_service.get_atencion(db_session, HOY)
    assert _claves(items) == set(), items


def test_cliente_sin_visita_reciente(db_session):
    """Un cliente activo sin visitas en 90 días requiere atención."""
    _cliente(db_session, "Abandonado")
    items = dashboard_service.get_atencion(db_session, HOY)
    assert "sin_visita" in _claves(items)

    sin_visita = next(i for i in items if i["clave"] == "sin_visita")
    assert sin_visita["cantidad"] == 1
    assert "Abandonado" in sin_visita["detalle"]
    assert sin_visita["enlace"].startswith("/clientes")


def test_cliente_con_visita_reciente_no_aparece(db_session):
    """Una visita dentro del plazo lo saca del panel."""
    _cliente(db_session, "Visitado")
    _visita(db_session, "Visitado", (HOY.date() - datetime.timedelta(days=10)).isoformat())
    items = dashboard_service.get_atencion(db_session, HOY)
    assert "sin_visita" not in _claves(items)


def test_cliente_inactivo_no_cuenta(db_session):
    """Un cliente dado de baja no requiere atención."""
    _cliente(db_session, "De baja", activo=False)
    items = dashboard_service.get_atencion(db_session, HOY)
    assert "sin_visita" not in _claves(items)


def test_maquinas_sin_relevamiento(db_session):
    c = _cliente(db_session, "Con máquinas")
    _maquina(db_session, c.id, RelevamientoStatus.PENDIENTE.value)
    _maquina(db_session, c.id, RelevamientoStatus.EN_PROCESO.value)
    _maquina(db_session, c.id, RelevamientoStatus.COMPLETADO.value)

    items = dashboard_service.get_atencion(db_session, HOY)
    assert "sin_relevar" in _claves(items)
    sin_relevar = next(i for i in items if i["clave"] == "sin_relevar")
    # Sólo las dos que no están completas.
    assert sin_relevar["cantidad"] == 2


def test_minuta_en_borrador_vieja(db_session):
    """Una minuta en borrador hace más de 15 días requiere atención."""
    _minuta(db_session, (HOY.date() - datetime.timedelta(days=30)).isoformat())
    items = dashboard_service.get_atencion(db_session, HOY)
    assert "minutas_borrador" in _claves(items)

    # Una reciente no.
    db_session.query(models.MeetingMinutes).delete()
    db_session.commit()
    _minuta(db_session, (HOY.date() - datetime.timedelta(days=2)).isoformat())
    assert "minutas_borrador" not in _claves(
        dashboard_service.get_atencion(db_session, HOY))


def test_minuta_finalizada_no_cuenta(db_session):
    _minuta(db_session, (HOY.date() - datetime.timedelta(days=30)).isoformat(),
            status="Finalizado")
    assert "minutas_borrador" not in _claves(
        dashboard_service.get_atencion(db_session, HOY))


def test_tarea_vencida(db_session):
    _tarea(db_session, (HOY.date() - datetime.timedelta(days=5)).isoformat())
    items = dashboard_service.get_atencion(db_session, HOY)
    assert "tareas_vencidas" in _claves(items)

    # Finalizada o cancelada no cuenta.
    db_session.query(models.ActionPlanTracking).delete()
    db_session.commit()
    _tarea(db_session, (HOY.date() - datetime.timedelta(days=5)).isoformat(),
           status=TrackingStatus.FINALIZADO.value)
    assert "tareas_vencidas" not in _claves(
        dashboard_service.get_atencion(db_session, HOY))


def test_lo_mas_urgente_va_primero(db_session):
    """El orden es peligro, alerta, info: lo urgente arriba."""
    c = _cliente(db_session, "Urgente")
    _maquina(db_session, c.id, RelevamientoStatus.PENDIENTE.value)
    _tarea(db_session, (HOY.date() - datetime.timedelta(days=1)).isoformat())

    items = dashboard_service.get_atencion(db_session, HOY)
    assert len(items) >= 2
    assert items[0]["tono"] == "peligro", items
    tonos = [i["tono"] for i in items]
    assert tonos == sorted(tonos, key=lambda t: {"peligro": 0, "alerta": 1, "info": 2}[t])


def test_el_panel_se_renderiza_en_el_dashboard(client, db_session, seed_admin):
    """Con algo pendiente, el panel aparece en la página."""
    _cliente(db_session, "Sin visitas nunca")
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    html = client.get("/").text
    assert "Requiere atención" in html
    assert "Sin visitas nunca" in html


def test_el_panel_no_se_renderiza_sin_pendientes(client, db_session, seed_admin):
    """Sin pendientes, el bloque no está en el HTML."""
    client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    html = client.get("/").text
    assert "Requiere atención" not in html
