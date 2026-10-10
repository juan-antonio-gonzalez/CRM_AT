from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
import models
from database import get_db
from services.customer_service import list_customers
from services import pagination as pg
import datetime
import json
from templating import templates

router = APIRouter(tags=["agenda"])


@router.get("/agenda", response_class=HTMLResponse)
async def agenda_view(request: Request, db: Session = Depends(get_db)):
    clientes = list_customers(db)
    tecnicos = db.query(models.TechnicalAdvisor).all()
    today = datetime.date.today().isoformat()

    # Build cliente → AT mapping from at_assignments (fallback to Customer.technical_advisor)
    cliente_at = {}
    ats_set = set()
    try:
        at_assignments = db.query(models.ATAssignment).filter(models.ATAssignment.valid_to.is_(None)).all()
        for a in at_assignments:
            if a.technical_advisor:
                ats_set.add(a.technical_advisor)
        at_map = {a.customer_name: a.technical_advisor for a in at_assignments if a.technical_advisor}
        # Fill missing from Customer table
        for c in clientes:
            ta = getattr(c, 'technical_advisor', None) or ''
            if c.name not in at_map and ta:
                at_map[c.name] = ta
                ats_set.add(ta)
        for c in clientes:
            if c.name in at_map:
                cliente_at[str(c.id)] = at_map[c.name]
    except Exception:
        cliente_at = {}

    # Ensure ATs from TechnicalAdvisor table are also included
    for t in tecnicos:
        if t.name:
            ats_set.add(t.name)
    ats_asignados = sorted(ats_set)

    return templates.TemplateResponse(request, 'agenda.html', {
        "request": request,
        "clientes": clientes,
        "tecnicos": tecnicos,
        "ats_asignados": ats_asignados,
        "cliente_at": cliente_at,
        "today": today,
        "active_page": "agenda"
    })


@router.get("/api/visitas-agenda", response_class=JSONResponse)
async def visitas_agenda_api(
    request: Request,
    start: str = Query(None),
    end: str = Query(None),
    cliente: str = Query(None, alias="cliente"),
    db: Session = Depends(get_db)
):
    query = db.query(models.TechnicalVisit2).filter(
        models.TechnicalVisit2.fecha != ""
    )
    if start:
        query = query.filter(models.TechnicalVisit2.fecha >= start)
    if end:
        query = query.filter(models.TechnicalVisit2.fecha <= end)
    if cliente:
        query = query.filter(
            models.TechnicalVisit2.form_data["cliente_id"].as_string() == cliente
        )
    visits = query.order_by(models.TechnicalVisit2.fecha).all()

    result = []
    for v in visits:
        fd = v.form_data or {}
        cliente_nombre = fd.get("cliente_nombre", "")
        objetivo = fd.get("objetivo", [])
        at = fd.get("at", "")
        swa_count = len(fd.get("swa", []))
        cli_count = len(fd.get("cli", []))

        if isinstance(objetivo, list):
            obj_labels = []
            for o in objetivo:
                label_map = {
                    "programada": "Visita Programada",
                    "Visita programada": "Visita Programada",
                    "no_conformidad": "No Conformidad",
                    "Análisis No conformidad": "No Conformidad",
                    "seguimiento": "Seguimiento",
                    "Seguimiento": "Seguimiento",
                    "solicitud": "Solicitud",
                    "Solicitud del cliente": "Solicitud",
                }
                obj_labels.append(label_map.get(o, o))
            objetivo_str = ", ".join(obj_labels)
        else:
            objetivo_str = ""

        result.append({
            "id": v.id,
            "title": cliente_nombre or f"Visita #{v.id}",
            "start": v.fecha,
            "status": v.status,
            "advisor": at,
            "objetivo": objetivo_str,
            "swa_count": swa_count,
            "cli_count": cli_count,
            "url": f"/visitas2/{v.id}/editar",
        })

    return result


@router.post("/api/agenda/cancelar-visita/{visit_id}")
async def cancelar_visita_desde_agenda(visit_id: int, request: Request, db: Session = Depends(get_db)):
    visit = db.query(models.TechnicalVisit2).filter(models.TechnicalVisit2.id == visit_id).first()
    if visit:
        visit.status = "Cancelado"
        fd = visit.form_data or {}
        fd["status"] = "Cancelado"
        visit.form_data = fd
        db.commit()
    return RedirectResponse(url="/agenda", status_code=303)


@router.post("/api/agenda/crear-visita")
async def crear_visita_desde_agenda(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data_raw = form.get("form_data", "{}")
    try:
        data = json.loads(form_data_raw)
    except (json.JSONDecodeError, TypeError):
        data = {}

    if not data.get("fecha") or not data.get("cliente_id"):
        return RedirectResponse(url="/agenda?error=campos_obligatorios", status_code=303)

    fecha = data.get("fecha", "")
    today = datetime.date.today().isoformat()
    if fecha < today:
        return RedirectResponse(url="/agenda?error=fecha_pasada", status_code=303)
    visit = models.TechnicalVisit2(
        fecha=fecha,
        status="Programado",
        form_data=data,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)

    return RedirectResponse(url="/agenda", status_code=303)
