from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
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
