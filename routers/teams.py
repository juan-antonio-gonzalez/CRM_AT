"""Pantalla de Equipos.

Todos los envíos van como formulario, no como JSON. El middleware de `main.py`
valida el CSRF sólo cuando el cuerpo es `form-urlencoded` o `multipart`; un
endpoint que reciba JSON no pasa por esa validación. Usar formularios hereda la
comprobación que ya existe y que ya está cubierta por `tests/test_csrf.py`, en
vez de reimplementarla en cada ruta.

Los errores de validación no se devuelven como JSON: se vuelve a renderizar la
pantalla con el mensaje y con lo que el usuario había escrito. Un equipo
incompleto es un error de tipeo, no una falla del servidor, y perder los tres
campos cargados por eso sería peor que el error.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

import models
from database import get_db
from services import auditoria, soft_delete as sd
from services import team_service
from templating import templates

router = APIRouter(tags=["equipos"])

# Dónde vive cada catálogo de personas, para poblar los tres selectores.
FUENTES = {
    "commercial": models.CommercialAdvisor,
    "designer": models.Designer,
    "technical_advisor": models.TechnicalAdvisor,
}


def _catalogos(db: Session) -> dict:
    """Las tres listas de personas, ordenadas y sólo las activas."""
    return {
        campo: (db.query(modelo)
                .filter(modelo.is_active.is_(True))
                .order_by(modelo.name)
                .all())
        for campo, modelo in FUENTES.items()
    }


def _catalogos_vacios(catalogos: dict) -> list[str]:
    return [team_service.ETIQUETAS_MIEMBRO[c] for c in team_service.MIEMBROS
            if not catalogos[c]]


def _pantalla(request: Request, db: Session, *, error: str = "", form: dict | None = None,
              modal: str = "", equipos=None, filtros: dict | None = None,
              status_code: int = 200):
    """Renderiza el listado, opcionalmente con un error y un modal reabierto.

    Los errores de validación vuelven a la misma pantalla con lo que el usuario
    había escrito. Devolver un JSON con el detalle sería más corto de escribir y
    le haría perder los cuatro campos cargados por un error de tipeo.
    """
    catalogos = _catalogos(db)
    return templates.TemplateResponse(request, "equipos.html", {
        "request": request,
        "active_page": "equipos",
        "equipos": equipos if equipos is not None else team_service.listar(db),
        "conteo": team_service.conteo_por_equipo(db),
        "repetidos": team_service.equipos_repetidos(db),
        "catalogos": catalogos,
        "catalogos_vacios": _catalogos_vacios(catalogos),
        "filtros": filtros or {"q": "", "estado": ""},
        "error": error,
        "modal_abierto": modal,
        "form": form or {},
    }, status_code=status_code)


@router.get("/equipos", response_class=HTMLResponse)
async def listar_equipos(
    request: Request,
    q: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filtros = {"q": q or "", "estado": estado or ""}
    return _pantalla(request, db,
                     equipos=team_service.listar(db, q=filtros["q"], estado=filtros["estado"]),
                     filtros=filtros)


@router.post("/equipos/nuevo")
async def crear_equipo(
    request: Request,
    name: str = Form(""),
    commercial: str = Form(""),
    designer: str = Form(""),
    technical_advisor: str = Form(""),
    observations: str = Form(""),
    db: Session = Depends(get_db),
):
    form = {"name": name, "commercial": commercial, "designer": designer,
            "technical_advisor": technical_advisor, "observations": observations}
    try:
        equipo = team_service.crear(db, name, commercial, designer,
                                    technical_advisor, observations)
    except HTTPException as exc:
        return _pantalla(request, db, error=exc.detail, form=form,
                         modal="nuevo", status_code=400)

    auditoria.registrar(db, "team", equipo.id, "crear",
                        user=getattr(request.state, "user", None),
                        entity_label=equipo.name)
    return RedirectResponse(url="/equipos", status_code=303)


@router.get("/equipos/{team_id}/editar", response_class=HTMLResponse)
async def formulario_edicion(team_id: int, request: Request,
                             db: Session = Depends(get_db)):
    equipo = team_service.obtener(db, team_id)
    catalogos = _catalogos(db)
    return templates.TemplateResponse(request, "editar_equipo.html", {
        "request": request,
        "active_page": "equipos",
        "equipo": equipo,
        "catalogos": catalogos,
        "catalogos_vacios": _catalogos_vacios(catalogos),
        "clientes": team_service.clientes_asignados(db, team_id),
    })


@router.post("/equipos/{team_id}/editar")
async def guardar_edicion(
    request: Request,
    team_id: int,
    name: str = Form(""),
    commercial: str = Form(""),
    designer: str = Form(""),
    technical_advisor: str = Form(""),
    observations: str = Form(""),
    db: Session = Depends(get_db),
):
    antes = auditoria.snapshot(team_service.obtener(db, team_id))
    try:
        team_service.actualizar(db, team_id, name, commercial, designer,
                                technical_advisor, observations)
    except HTTPException as exc:
        catalogos = _catalogos(db)
        return templates.TemplateResponse(request, "editar_equipo.html", {
            "request": request,
            "active_page": "equipos",
            "equipo": team_service.obtener(db, team_id),
            "catalogos": catalogos,
            "catalogos_vacios": _catalogos_vacios(catalogos),
            "clientes": team_service.clientes_asignados(db, team_id),
            "error": exc.detail,
            "form": {"name": name, "commercial": commercial, "designer": designer,
                     "technical_advisor": technical_advisor,
                     "observations": observations},
        }, status_code=400)

    cambios = auditoria.diferencias(
        antes, auditoria.snapshot(team_service.obtener(db, team_id)))
    if cambios:
        auditoria.registrar(db, "team", team_id, "editar",
                            user=getattr(request.state, "user", None),
                            entity_label=name, changes=cambios)

    # Editar un equipo **no** toca a los clientes que ya lo tenían: la asignación
    # es una foto del momento. Se avisa en la pantalla de edición, no acá.
    return RedirectResponse(url="/equipos", status_code=303)


@router.post("/equipos/{team_id}/desactivar")
async def desactivar_equipo(
    team_id: int,
    request: Request,
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "user", None)
    uid = int(user["sub"]) if user and user.get("sub") else None
    equipo = team_service.obtener(db, team_id)

    try:
        sd.soft_deactivate(db, models.Team, team_id, reason, uid)
    except HTTPException as exc:
        # Sin modal: el error de una desactivación se lee arriba del listado.
        return _pantalla(request, db, error=exc.detail, status_code=400)

    auditoria.registrar(db, "team", team_id, "desactivar", user=user,
                        entity_label=equipo.name,
                        changes={"motivo": {"antes": "", "despues": reason}})
    return RedirectResponse(url="/equipos", status_code=303)


@router.post("/equipos/{team_id}/actualizar-asignaciones")
async def actualizar_asignaciones(team_id: int, request: Request,
                                  db: Session = Depends(get_db)):
    """Reaplica el equipo a sus clientes.

    Asignar guarda una foto: editar el equipo no reescribe a los clientes que ya lo
    tenían. Esta es la acción que sí lo hace, y es explícita justamente para que
    nadie reescriba informes viejos sin querer.
    """
    user = getattr(request.state, "user", None)
    equipo = team_service.obtener(db, team_id)
    resultado = team_service.actualizar_asignaciones(db, team_id)

    auditoria.registrar(
        db, "team", team_id, "actualizar", user=user, entity_label=equipo.name,
        changes={"asignaciones": {
            "antes": "",
            "despues": f"{resultado['clientes']} cliente(s), "
                       f"{resultado['asignaciones']} asignación(es) AT",
        }})
    return RedirectResponse(url="/equipos", status_code=303)


@router.post("/equipos/{team_id}/reactivar")
async def reactivar_equipo(team_id: int, request: Request,
                           db: Session = Depends(get_db)):
    user = getattr(request.state, "user", None)
    if (user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo el admin puede reactivar")

    equipo = team_service.obtener(db, team_id)
    sd.soft_reactivate(db, models.Team, team_id)
    auditoria.registrar(db, "team", team_id, "reactivar", user=user,
                        entity_label=equipo.name)
    return RedirectResponse(url="/equipos", status_code=303)
