from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from sqlalchemy import func
import models
from database import get_db
from services import visit_service, pagination as pg
from enums import VisitStatus
import datetime
import json

router = APIRouter(tags=["visits"])
templates = Jinja2Templates(directory="templates")


@router.get("/visitas", response_class=HTMLResponse)
async def visitas_lista(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    page, per_page, offset = pg.paginate(page, per_page)
    total = db.query(func.count(models.TechnicalVisit.id)).scalar() or 0
    visits = db.query(models.TechnicalVisit).order_by(
        models.TechnicalVisit.date.desc()
    ).offset(offset).limit(per_page).all()

    now = datetime.datetime.now(datetime.UTC)
    total_month = db.query(func.count(models.TechnicalVisit.id)).filter(
        func.strftime('%m', models.TechnicalVisit.date) == f"{now.month:02d}",
        func.strftime('%Y', models.TechnicalVisit.date) == str(now.year)
    ).scalar() or 0
    pendientes = db.query(func.count(models.TechnicalVisit.id)).filter(
        models.TechnicalVisit.status == VisitStatus.PROGRAMADA.value
    ).scalar() or 0
    completed = db.query(func.count(models.TechnicalVisit.id)).filter(
        models.TechnicalVisit.status == VisitStatus.FINALIZADA.value
    ).scalar() or 0

    return templates.TemplateResponse("visitas_lista.html", {
        "request": request,
        "visits": visits,
        "stats": {"total_month": total_month, "pendientes": pendientes, "completadas": completed},
        "pagination": pg.build_pagination(page, per_page, total),
        "active_page": "visitas"
    })


@router.get("/visitas/nueva", response_class=HTMLResponse)
async def nueva_visita(request: Request, db: Session = Depends(get_db)):
    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))
    topics = db.query(models.VisitTopic).order_by(models.VisitTopic.name).all()
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    visit_types = db.query(models.VisitType).order_by(models.VisitType.name).all()
    distributor_plants = db.query(models.DistributorPlant).order_by(models.DistributorPlant.name).all()

    return templates.TemplateResponse("nueva_visita.html", {
        "request": request,
        "unique_customer_names": unique_customer_names,
        "topics": topics,
        "advisors": advisors,
        "visit_types": visit_types,
        "distributor_plants": distributor_plants,
        "active_page": "visitas"
    })


@router.post("/visitas/nueva")
async def create_visita(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    customer_name = form_data.get("customer_id")
    if not customer_name:
        return RedirectResponse(url="/visitas/nueva", status_code=303)

    plant_name = form_data.get("plant_assigned")
    saved_photos = await visit_service.process_visit_photos(
        form_data.getlist("photos_asistencia") + form_data.getlist("photos_registro")
    )

    new_visit = visit_service.create_visit_from_form(db, form_data, customer_name, plant_name)
    if not new_visit:
        return RedirectResponse(url="/visitas/nueva", status_code=303)

    new_visit.evidence_photos = saved_photos
    db.commit()

    if form_data.get("preview_mode") == "true":
        return RedirectResponse(url=f"/visitas/{new_visit.id}/reporte?preview=true", status_code=303)
    return RedirectResponse(url="/visitas", status_code=303)


@router.get("/visitas/{visit_id}/editar", response_class=HTMLResponse)
async def editar_visita(request: Request, visit_id: int, db: Session = Depends(get_db)):
    visit = visit_service.get_visit(db, visit_id)
    if not visit:
        return RedirectResponse(url="/visitas", status_code=303)

    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))
    topics = db.query(models.VisitTopic).order_by(models.VisitTopic.name).all()
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    visit_types = db.query(models.VisitType).order_by(models.VisitType.name).all()
    distributor_plants = db.query(models.DistributorPlant).order_by(models.DistributorPlant.name).all()

    return templates.TemplateResponse("editar_visita.html", {
        "request": request,
        "visit": visit,
        "unique_customer_names": unique_customer_names,
        "topics": topics,
        "advisors": advisors,
        "visit_types": visit_types,
        "distributor_plants": distributor_plants,
        "active_page": "visitas"
    })


@router.post("/visitas/{visit_id}/editar")
async def save_editar_visita(visit_id: int, request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    new_photos = await visit_service.process_visit_photos(
        form_data.getlist("photos_asistencia") + form_data.getlist("photos_registro")
    )

    visit = visit_service.update_visit_from_form(db, visit_id, form_data)
    if not visit:
        return RedirectResponse(url="/visitas", status_code=303)

    if new_photos:
        current_photos = list(visit.evidence_photos) if visit.evidence_photos else []
        current_photos.extend(new_photos)
        visit.evidence_photos = current_photos
        db.commit()

    if form_data.get("preview_mode") == "true":
        return RedirectResponse(url=f"/visitas/{visit_id}/reporte?preview=true", status_code=303)
    return RedirectResponse(url="/visitas", status_code=303)


@router.post("/eliminar-visita/{visit_id}")
async def delete_visita(visit_id: int, request: Request, db: Session = Depends(get_db)):
    user = getattr(request.state, 'user', None)
    uid = int(user["sub"]) if user else None
    uname = user.get("username") if user else None
    visit_service.delete_visit(db, visit_id, uid, uname)
    return RedirectResponse(url="/visitas", status_code=303)


@router.get("/agenda", response_class=HTMLResponse)
async def view_agenda(request: Request, db: Session = Depends(get_db)):
    customers = db.query(models.Customer).all()
    unique_customer_names = sorted(list(set([c.name for c in customers])))
    topics = db.query(models.VisitTopic).all()
    return templates.TemplateResponse("agenda.html", {
        "request": request,
        "active_page": "agenda",
        "unique_customer_names": unique_customer_names,
        "topics": topics
    })


@router.get("/api/visitas-agenda")
async def get_visitas_agenda(db: Session = Depends(get_db)):
    return visit_service.get_agenda_events(db)


@router.post("/api/visitas/{visit_id}/status")
async def update_visit_status(visit_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    return visit_service.update_visit_status(db, visit_id, data.get("status"), data.get("reason"))


@router.get("/visitas/{visit_id}/reporte", response_class=HTMLResponse)
async def reporte_visita(request: Request, visit_id: int, db: Session = Depends(get_db)):
    visit = visit_service.get_visit(db, visit_id)
    if not visit:
        return RedirectResponse(url="/visitas", status_code=303)

    action_plan = []
    if visit.action_plan:
        try:
            action_plan = json.loads(visit.action_plan)
        except:
            pass

    return templates.TemplateResponse("visitas_reporte.html", {
        "request": request,
        "visit": visit,
        "action_plan": action_plan,
        "active_page": "visitas"
    })
