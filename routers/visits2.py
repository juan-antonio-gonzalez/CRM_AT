from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import models
from database import get_db
from services import pagination as pg
from services.utils import safe_json_loads
from services.customer_service import list_customers
import datetime

from enums import TrackingStatus
from templating import templates

router = APIRouter(tags=["visits2"])


def cliente_nombre_planta(cliente_text: str) -> tuple:
    """Extract name and plant from 'Name (Plant)' format."""
    if not cliente_text:
        return "", ""
    if "(" in cliente_text:
        name = cliente_text.split("(")[0].strip()
        plant = cliente_text.split("(")[1].rstrip(")").strip()
        return name, plant
    return cliente_text, ""


def sync_action_plan(db: Session, visit_id: int, data: dict):
    """Sync Table 9 (ACCIONES) rows into action_plan_tracking.

    Implemented as an upsert keyed on (source_visit_id, et_number, task).

    The previous version deleted every tracking row for the visit and recreated
    them with ``status=PENDIENTE``, so any progress and observations the user had
    recorded in /seguimiento-plan were silently wiped on the next save.
    """
    tables = data.get("tables", {})
    rows = tables.get("9", [])

    cliente_nombre, cliente_planta = cliente_nombre_planta(data.get("cliente_nombre", ""))

    existing = db.query(models.ActionPlanTracking).filter(
        models.ActionPlanTracking.source_visit_id == visit_id
    ).all()
    existing_by_key = {(r.et_number or "", r.task or ""): r for r in existing}
    seen_keys = set()

    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 4:
            continue
        et = (row[0] or "").strip()
        accion = (row[1] or "").strip()
        responsable = (row[2] or "").strip()
        plazo = (row[3] or "").strip()

        if not accion:
            continue  # skip empty action rows

        key = (et, accion)
        seen_keys.add(key)
        record = existing_by_key.get(key)

        if record:
            # Preserve status/observations owned by the seguimiento-plan screen.
            record.responsible = responsable
            record.due_date = plazo
            record.customer_name = cliente_nombre
            record.plant = cliente_planta
            record.updated_at = datetime.datetime.now()
        else:
            db.add(models.ActionPlanTracking(
                customer_name=cliente_nombre,
                plant=cliente_planta,
                visit_date=datetime.datetime.now(),
                et_number=et,
                task=accion,
                responsible=responsable,
                due_date=plazo,
                status=TrackingStatus.PENDIENTE.value,
                source_visit_id=visit_id,
                is_active=True,
            ))

    # Rows removed from the form are deactivated rather than deleted, so their
    # history and any recorded progress survive.
    for key, record in existing_by_key.items():
        if key not in seen_keys and record.is_active:
            record.is_active = False
            record.inactivation_reason = "Acción eliminada de la visita"
            record.inactivated_at = datetime.datetime.now()


@router.get("/visitas2", response_class=HTMLResponse)
async def visitas2_lista(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("fecha_desc"),
    db: Session = Depends(get_db)
):
    page, per_page, offset = pg.paginate(page, per_page)
    total = db.query(func.count(models.TechnicalVisit2.id)).scalar() or 0
    if sort == "fecha_asc":
        order = models.TechnicalVisit2.fecha.asc()
    else:
        order = models.TechnicalVisit2.fecha.desc()
        sort = "fecha_desc"
    visits = db.query(models.TechnicalVisit2).order_by(
        order
    ).offset(offset).limit(per_page).all()

    today = datetime.date.today().isoformat()

    q = db.query(models.TechnicalVisit2)
    hechas = q.filter(models.TechnicalVisit2.status == "Finalizado").count()
    programadas = q.filter(models.TechnicalVisit2.status == "Programado").count()
    pendientes = q.filter(models.TechnicalVisit2.status == "En proceso").count()
    canceladas = q.filter(models.TechnicalVisit2.status == "Cancelado").count()

    return templates.TemplateResponse(request, 'visitas2_lista.html', {
        "request": request,
        "visits": visits,
        "pagination": pg.build_pagination(page, per_page, total),
        "stats": {
            "hechas": hechas,
            "programadas": programadas,
            "pendientes": pendientes,
            "canceladas": canceladas,
        },
        "active_page": "visitas2",
        "sort": sort
    })


@router.get("/visitas2/nueva", response_class=HTMLResponse)
async def nueva_visita2(request: Request, db: Session = Depends(get_db)):
    clientes = list_customers(db)
    tecnicos = db.query(models.TechnicalAdvisor).all()
    distribuidoras = db.query(models.DistributorPlant).order_by(models.DistributorPlant.name).all()
    temas_calidad = db.query(models.QualityTopic).order_by(models.QualityTopic.name).all()
    calidad_at = db.query(models.QualityAT).order_by(models.QualityAT.name).all()
    return templates.TemplateResponse(request, 'nueva_visita2.html', {
        "request": request,
        "visit": None,
        "form_data": None,
        "title": "Nueva Visita Técnica V2",
        "action_url": "/visitas2/nueva",
        "active_page": "visitas2",
        "clientes": clientes,
        "tecnicos": tecnicos,
        "distribuidoras": distribuidoras,
        "temas_calidad": temas_calidad,
        "calidad_at": calidad_at
    })


@router.post("/visitas2/nueva")
async def create_visita2(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    data = safe_json_loads(form.get("form_data"))

    fecha = data.get("fecha", "") or ""
    estado = data.get("status", "En proceso")
    new_visit = models.TechnicalVisit2(
        fecha=fecha,
        status=estado,
        form_data=data,
    )
    db.add(new_visit)
    db.commit()
    db.refresh(new_visit)

    sync_action_plan(db, new_visit.id, data)
    db.commit()

    return RedirectResponse(url="/visitas2", status_code=303)


@router.get("/visitas2/{visit_id}/editar", response_class=HTMLResponse)
async def editar_visita2(request: Request, visit_id: int, db: Session = Depends(get_db)):
    visit = db.query(models.TechnicalVisit2).filter(models.TechnicalVisit2.id == visit_id).first()
    if not visit:
        return RedirectResponse(url="/visitas2", status_code=303)

    clientes = list_customers(db)
    tecnicos = db.query(models.TechnicalAdvisor).all()
    distribuidoras = db.query(models.DistributorPlant).order_by(models.DistributorPlant.name).all()
    temas_calidad = db.query(models.QualityTopic).order_by(models.QualityTopic.name).all()
    calidad_at = db.query(models.QualityAT).order_by(models.QualityAT.name).all()
    return templates.TemplateResponse(request, 'nueva_visita2.html', {
        "request": request,
        "visit": visit,
        "form_data": visit.form_data or {},
        "title": f"Editar Visita V2 #{visit.id}",
        "action_url": f"/visitas2/{visit_id}/editar",
        "active_page": "visitas2",
        "clientes": clientes,
        "tecnicos": tecnicos,
        "distribuidoras": distribuidoras,
        "temas_calidad": temas_calidad,
        "calidad_at": calidad_at
    })


@router.post("/visitas2/{visit_id}/editar")
async def save_editar_visita2(visit_id: int, request: Request, db: Session = Depends(get_db)):
    visit = db.query(models.TechnicalVisit2).filter(models.TechnicalVisit2.id == visit_id).first()
    if not visit:
        return RedirectResponse(url="/visitas2", status_code=303)

    form = await request.form()
    data = safe_json_loads(form.get("form_data"))

    visit.fecha = data.get("fecha", "") or ""
    visit.status = data.get("status", "En proceso")
    visit.form_data = data
    visit.updated_at = datetime.datetime.utcnow()
    db.commit()

    sync_action_plan(db, visit.id, data)
    db.commit()

    return RedirectResponse(url="/visitas2", status_code=303)


@router.post("/cancelar-visita2/{visit_id}")
async def cancel_visita2(visit_id: int, request: Request, db: Session = Depends(get_db)):
    visit = db.query(models.TechnicalVisit2).filter(models.TechnicalVisit2.id == visit_id).first()
    if visit:
        visit.status = "Cancelado"
        fd = visit.form_data or {}
        fd["status"] = "Cancelado"
        visit.form_data = fd
        db.commit()
    return RedirectResponse(url="/visitas2", status_code=303)


@router.post("/eliminar-visita2/{visit_id}")
async def delete_visita2(visit_id: int, request: Request, db: Session = Depends(get_db)):
    visit = db.query(models.TechnicalVisit2).filter(models.TechnicalVisit2.id == visit_id).first()
    if visit:
        from services.trash_service import move_to_trash
        user = getattr(request.state, 'user', None)
        uid = int(user["sub"]) if user else None
        uname = user.get("username") if user else None
        fd = visit.form_data or {}
        move_to_trash(db, "visit2", visit.id, {
            "id": visit.id,
            "fecha": visit.fecha,
            "status": visit.status,
            "form_data": fd,
            "cliente_nombre": fd.get("cliente_nombre", ""),
        }, uid, uname, f"Visita #{visit.id}")
        db.delete(visit)
        db.commit()
    return RedirectResponse(url="/visitas2", status_code=303)
