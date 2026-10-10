from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from sqlalchemy import func
import models
from database import get_db
from services import survey_service
from enums import SurveyStatus
from templating import templates

router = APIRouter(tags=["infraestructura"])


@router.get("/relevamiento-infraestructura", response_class=HTMLResponse)
async def infraestructura_lista(
    request: Request,
    cliente: Optional[int] = Query(None),
    asistente: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    surveys, customers, advisors, pagination = survey_service.list_infrastructure_surveys(
        db, cliente, asistente, page, per_page
    )

    completados = db.query(func.count(models.InfrastructureSurvey.id)).filter(models.InfrastructureSurvey.status == SurveyStatus.COMPLETADO.value).scalar() or 0
    en_proceso = db.query(func.count(models.InfrastructureSurvey.id)).filter(models.InfrastructureSurvey.status == SurveyStatus.EN_PROCESO.value).scalar() or 0
    pendientes = db.query(func.count(models.InfrastructureSurvey.id)).filter(models.InfrastructureSurvey.status == SurveyStatus.PENDIENTE.value).scalar() or 0
    stats = {
        "total": completados + en_proceso + pendientes,
        "completados": completados,
        "en_proceso": en_proceso,
        "pendientes": pendientes
    }

    return templates.TemplateResponse(request, 'relevamiento_infraestructura_lista.html', {
        "request": request,
        "surveys": surveys,
        "pagination": pagination,
        "customers": customers,
        "advisors": advisors,
        "selected_customer_id": cliente,
        "selected_asistente": asistente,
        "stats": stats,
        "active_page": "infraestructura"
    })


@router.get("/relevamiento-infraestructura/nuevo", response_class=HTMLResponse)
async def infraestructura_nuevo(request: Request, db: Session = Depends(get_db)):
    customers = db.query(models.Customer).order_by(models.Customer.name).all()
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    unique_customer_names = sorted(list(set(c.name for c in customers)))
    return templates.TemplateResponse(request, 'relevamiento_infraestructura_form.html', {
        "request": request,
        "customers": customers,
        "unique_customer_names": unique_customer_names,
        "advisors": advisors,
        "survey": None,
        "active_page": "infraestructura"
    })


@router.get("/relevamiento-infraestructura/{survey_id:int}", response_class=HTMLResponse)
async def infraestructura_editar(request: Request, survey_id: int, db: Session = Depends(get_db)):
    customers = db.query(models.Customer).order_by(models.Customer.name).all()
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    unique_customer_names = sorted(list(set(c.name for c in customers)))

    survey = db.query(models.InfrastructureSurvey).filter(models.InfrastructureSurvey.id == survey_id).first()
    if not survey:
        return RedirectResponse(url="/relevamiento-infraestructura")

    current_customer = db.query(models.Customer).filter(models.Customer.id == survey.customer_id).first()
    current_customer_name = current_customer.name if current_customer else ""

    return templates.TemplateResponse(request, 'relevamiento_infraestructura_form.html', {
        "request": request,
        "customers": customers,
        "unique_customer_names": unique_customer_names,
        "advisors": advisors,
        "survey": survey,
        "current_customer_name": current_customer_name,
        "active_page": "infraestructura"
    })


@router.post("/relevamiento-infraestructura")
@router.post("/relevamiento-infraestructura/{survey_id:int}")
async def save_infraestructura(request: Request, survey_id: Optional[int] = None, db: Session = Depends(get_db)):
    form_data = await request.form()
    data_dict = dict(form_data)
    survey_service.save_infrastructure_survey(db, data_dict, survey_id)

    if data_dict.get("preview_mode") == "true":
        return RedirectResponse(url=f"/relevamiento-infraestructura/{survey_id or '0'}/reporte?preview=true", status_code=303)
    return RedirectResponse(url="/relevamiento-infraestructura", status_code=303)


@router.get("/relevamiento-infraestructura/{survey_id}/reporte", response_class=HTMLResponse)
async def reporte_infraestructura(request: Request, survey_id: int, db: Session = Depends(get_db)):
    survey = db.query(models.InfrastructureSurvey).filter(models.InfrastructureSurvey.id == survey_id).first()
    if not survey:
        return RedirectResponse(url="/relevamiento-infraestructura", status_code=303)

    return templates.TemplateResponse(request, 'infraestructura_reporte.html', {
        "request": request,
        "survey": survey,
        "active_page": "infraestructura"
    })


@router.post("/relevamiento-infraestructura/eliminar/{survey_id}")
async def delete_infraestructura(survey_id: int, request: Request, db: Session = Depends(get_db)):
    user = getattr(request.state, 'user', None)
    uid = int(user["sub"]) if user else None
    uname = user.get("username") if user else None
    survey_service.delete_infrastructure_survey(db, survey_id, uid, uname)
    return RedirectResponse(url="/relevamiento-infraestructura", status_code=303)
