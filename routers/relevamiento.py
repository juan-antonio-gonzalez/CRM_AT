from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
import models
from database import get_db
from services import survey_service
from templating import templates

router = APIRouter(tags=["relevamiento"])


@router.get("/relevamiento", response_class=HTMLResponse)
async def relevamiento_list():
    return RedirectResponse(url="/relevamiento2", status_code=303)


@router.get("/relevamiento/{machine_id}/ver", response_class=HTMLResponse)
async def relevamiento_view(machine_id: int, request: Request, db: Session = Depends(get_db)):
    machine, survey = survey_service.get_machine_with_survey(db, machine_id)
    customer = machine.customer
    survey_data = survey.data if survey else {}

    return templates.TemplateResponse(request, 'relevamiento_ver.html', {
        "request": request, "machine": machine, "customer": customer,
        "survey": survey, "survey_data": survey_data,
        "active_page": "relevamiento"
    })


@router.get("/relevamiento/{machine_id}", response_class=HTMLResponse)
async def relevamiento_form(machine_id: int, request: Request, db: Session = Depends(get_db)):
    machine, survey = survey_service.get_machine_with_survey(db, machine_id)
    customer = machine.customer
    survey_data = survey.data if survey else {}

    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    designers = db.query(models.Designer).order_by(models.Designer.name).all()
    commercials = db.query(models.CommercialAdvisor).order_by(models.CommercialAdvisor.name).all()
    sectors = db.query(models.IndustrialSector).order_by(models.IndustrialSector.name).all()
    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))

    return templates.TemplateResponse(request, 'relevamiento.html', {
        "request": request, "machine": machine, "customer": customer,
        "survey": survey, "survey_data": survey_data,
        "advisors": advisors, "designers": designers,
        "commercials": commercials, "sectors": sectors,
        "unique_customer_names": unique_customer_names,
        "active_page": "relevamiento"
    })


@router.get("/relevamiento/{machine_id}/partial", response_class=HTMLResponse)
async def relevamiento_partial(machine_id: int, request: Request, db: Session = Depends(get_db)):
    machine, survey = survey_service.get_machine_with_survey(db, machine_id)
    customer = machine.customer
    survey_data = survey.data if survey else {}

    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    designers = db.query(models.Designer).order_by(models.Designer.name).all()
    commercials = db.query(models.CommercialAdvisor).order_by(models.CommercialAdvisor.name).all()
    sectors = db.query(models.IndustrialSector).order_by(models.IndustrialSector.name).all()
    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))
    formado_types = db.query(models.FormadoType).order_by(models.FormadoType.name).all()
    inferior_closure_types = db.query(models.InferiorClosure).order_by(models.InferiorClosure.name).all()

    return templates.TemplateResponse(request, '_relevamiento_partial.html', {
        "request": request, "machine": machine, "customer": customer,
        "survey": survey, "survey_data": survey_data,
        "advisors": advisors, "designers": designers,
        "commercials": commercials, "sectors": sectors,
        "unique_customer_names": unique_customer_names,
        "formado_types": formado_types,
        "inferior_closure_types": inferior_closure_types,
    })


@router.post("/relevamiento/{machine_id}")
async def save_relevamiento(machine_id: int, request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    data_dict = {}
    for key in form_data.keys():
        values = form_data.getlist(key)
        data_dict[key] = values if len(values) > 1 else values[0]

    is_finalize = data_dict.get("finalize") == "true"
    survey_service.save_relevamiento(db, machine_id, data_dict, is_finalize)

    if data_dict.get("preview_mode") == "true":
        return RedirectResponse(url=f"/relevamiento/{machine_id}/reporte?preview=true", status_code=303)
    return RedirectResponse(url="/relevamiento", status_code=303)


@router.get("/relevamiento/{machine_id}/reporte", response_class=HTMLResponse)
async def relevamiento_reporte(request: Request, machine_id: int, db: Session = Depends(get_db)):
    machine, survey = survey_service.get_machine_with_survey(db, machine_id)
    customer = machine.customer
    survey_data = survey.data if survey else {}

    return templates.TemplateResponse(request, 'relevamiento_reporte.html', {
        "request": request,
        "machine": machine,
        "customer": customer,
        "survey": survey,
        "survey_data": survey_data,
        "active_page": "relevamiento"
    })
