from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from services import tracking_service

router = APIRouter(tags=["seguimiento"])
templates = Jinja2Templates(directory="templates")


@router.get("/seguimiento-plan", response_class=HTMLResponse)
async def seguimiento_plan_lista(request: Request, db: Session = Depends(get_db)):
    trackings = tracking_service.list_trackings(db)
    total_tareas, finalizadas, pendientes, en_curso = tracking_service.get_tracking_stats(trackings)

    return templates.TemplateResponse("seguimiento_plan.html", {
        "request": request,
        "trackings": trackings,
        "active_page": "seguimiento",
        "total_tareas": total_tareas,
        "finalizadas": finalizadas,
        "pendientes": pendientes,
        "en_curso": en_curso
    })


@router.post("/seguimiento-plan/{track_id}/editar")
async def editar_seguimiento(request: Request, track_id: int, db: Session = Depends(get_db)):
    form_data = await request.form()
    tracking_service.update_tracking(db, track_id, form_data)
    return RedirectResponse(url="/seguimiento-plan", status_code=303)


@router.post("/seguimiento-plan/{track_id}/eliminar")
async def eliminar_seguimiento(track_id: int, db: Session = Depends(get_db)):
    tracking_service.delete_tracking(db, track_id)
    return RedirectResponse(url="/seguimiento-plan", status_code=303)
