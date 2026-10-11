from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import models
from database import get_db
from logger import get_logger
from services import tracking_service
from services.customer_service import list_customers
from templating import templates

logger = get_logger(__name__)

router = APIRouter(tags=["seguimiento"])


@router.get("/seguimiento-plan/exportar-excel")
async def exportar_seguimiento_excel(
    q: str = Query(None),
    estado: str = Query(None),
    db: Session = Depends(get_db),
):
    """Exporta el plan de acción filtrado a Excel."""
    from services.excel import hoja_excel, nombre_con_fecha

    tareas = (
        tracking_service.query_trackings(db, q=q, estado=estado)
        .order_by(models.ActionPlanTracking.created_at.desc())
        .all()
    )

    filas = [[
        t.customer_name, t.plant, t.visit_date, t.et_number, t.task,
        t.responsible, t.due_date, t.status, t.observations,
    ] for t in tareas]

    return hoja_excel(
        "Plan de acción",
        ["Cliente", "Planta", "Fecha de visita", "Nº ET", "Tarea", "Responsable",
         "Vence", "Estado", "Observaciones"],
        filas,
        nombre_con_fecha("seguimiento-plan"),
    )


@router.get("/seguimiento-plan", response_class=HTMLResponse)
async def seguimiento_plan_lista(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    q: str = Query(None),
    estado: str = Query(None),
    db: Session = Depends(get_db)
):
    trackings, pagination = tracking_service.paginate_trackings(
        db, page, per_page, q=q, estado=estado
    )
    total_tareas, finalizadas, pendientes, en_curso = tracking_service.get_tracking_stats(db)
    clientes = list_customers(db)

    return templates.TemplateResponse(request, 'seguimiento_plan.html', {
        "request": request,
        "trackings": trackings,
        "pagination": pagination,
        "active_page": "seguimiento",
        "total_tareas": total_tareas,
        "finalizadas": finalizadas,
        "pendientes": pendientes,
        "en_curso": en_curso,
        "q": q or "",
        "estado": estado or "",
        "clientes": clientes,
    })


@router.post("/seguimiento-plan/nueva")
async def crear_seguimiento(request: Request, db: Session = Depends(get_db)):
    """Crea una tarea del plan de acción cargada manualmente.

    Antes las tareas sólo nacían de la tabla 9 de una visita técnica, así que no
    había forma de registrar una acción surgida de una llamada, un correo o una
    reunión: faltaba la "C" del CRUD en este módulo.
    """
    form_data = await request.form()
    try:
        tracking_service.create_tracking(db, form_data)
    except ValueError as exc:
        logger.warning("No se pudo crear la tarea de seguimiento: %s", exc)
        return RedirectResponse(url="/seguimiento-plan?error=1", status_code=303)
    return RedirectResponse(url="/seguimiento-plan?ok=creada", status_code=303)


@router.post("/seguimiento-plan/{track_id}/editar")
async def editar_seguimiento(request: Request, track_id: int, db: Session = Depends(get_db)):
    form_data = await request.form()
    tracking_service.update_tracking(db, track_id, form_data)
    return RedirectResponse(url="/seguimiento-plan?ok=actualizada", status_code=303)


@router.post("/seguimiento-plan/{track_id}/eliminar")
async def eliminar_seguimiento(track_id: int, db: Session = Depends(get_db)):
    tracking_service.delete_tracking(db, track_id)
    return RedirectResponse(url="/seguimiento-plan?ok=eliminada", status_code=303)
