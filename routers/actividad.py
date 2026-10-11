"""Historial de cambios.

Dos vistas sobre la misma tabla: la global —qué pasó en el sistema— y la de un
registro puntual, que es la que responde "¿quién tocó esto?".
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

import models
from database import get_db
from services import auditoria
from templating import templates

router = APIRouter(tags=["actividad"])


@router.get("/historial-cambios", response_class=HTMLResponse)
async def historial_cambios(
    request: Request,
    entidad: str = Query(""),
    usuario: str = Query(""),
    accion: str = Query(""),
    db: Session = Depends(get_db),
):
    consulta = db.query(models.ActivityLog)
    if entidad:
        consulta = consulta.filter(models.ActivityLog.entity == entidad)
    if usuario:
        consulta = consulta.filter(models.ActivityLog.username == usuario)
    if accion:
        consulta = consulta.filter(models.ActivityLog.action == accion)

    registros = (
        consulta.order_by(models.ActivityLog.created_at.desc(),
                          models.ActivityLog.id.desc())
        .limit(300)
        .all()
    )

    # Las opciones de los filtros salen de lo que hay registrado, no de una lista
    # fija: si mañana se audita otra entidad, aparece sola.
    entidades = [e for (e,) in db.query(models.ActivityLog.entity).distinct().all() if e]
    usuarios = [u for (u,) in db.query(models.ActivityLog.username).distinct().all() if u]

    return templates.TemplateResponse(request, "historial_cambios.html", {
        "request": request,
        "active_page": "historial_cambios",
        "registros": registros,
        "filtros": {"entidad": entidad, "usuario": usuario, "accion": accion},
        "entidades": sorted(entidades),
        "usuarios": sorted(usuarios),
        "etiquetas": auditoria.ETIQUETAS,
        "acciones": auditoria.ACCIONES,
    })


@router.get("/api/historial/{entity}/{entity_id}")
async def historial_de_registro(entity: str, entity_id: int,
                                db: Session = Depends(get_db)):
    """Historial de un registro, para mostrarlo sin recargar la página."""
    registros = auditoria.historial(db, entity, entity_id)
    return JSONResponse({
        "entity": entity,
        "entity_id": entity_id,
        "registros": [{
            "accion": r.action,
            "accion_texto": auditoria.ACCIONES.get(r.action, r.action),
            "usuario": r.username or "—",
            "fecha": r.created_at.strftime("%d/%m/%Y %H:%M") if r.created_at else "",
            "resumen": auditoria.resumen(r),
            "cambios": r.changes or {},
        } for r in registros],
    })
