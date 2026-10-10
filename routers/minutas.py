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
from templating import templates

router = APIRouter(tags=["minutas"])


@router.get("/minutas", response_class=HTMLResponse)
async def minutas_lista(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    page, per_page, offset = pg.paginate(page, per_page)
    total = db.query(func.count(models.MeetingMinutes.id)).scalar() or 0
    minutas = db.query(models.MeetingMinutes).order_by(
        models.MeetingMinutes.id.desc()
    ).offset(offset).limit(per_page).all()

    finalizadas = db.query(models.MeetingMinutes).filter(
        models.MeetingMinutes.status == "Finalizado"
    ).count()
    borradores = db.query(models.MeetingMinutes).filter(
        models.MeetingMinutes.status == "Borrador"
    ).count()

    return templates.TemplateResponse(request, 'minutas_lista.html', {
        "request": request,
        "minutas": minutas,
        "pagination": pg.build_pagination(page, per_page, total),
        "stats": {
            "total": total,
            "finalizadas": finalizadas,
            "borradores": borradores,
        },
        "active_page": "minutas"
    })


@router.get("/minutas/nueva", response_class=HTMLResponse)
async def nueva_minuta(request: Request, db: Session = Depends(get_db)):
    clientes = list_customers(db)
    return templates.TemplateResponse(request, 'nueva_minuta.html', {
        "request": request,
        "minuta": None,
        "form_data": None,
        "title": "Nueva Minuta de Reunión",
        "action_url": "/minutas/nueva",
        "active_page": "minutas",
        "clientes": clientes,
    })


@router.post("/minutas/nueva")
async def create_minuta(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    data = safe_json_loads(form.get("form_data"))

    fecha = data.get("fecha", "") or ""
    estado = data.get("status", "Borrador")
    new_minuta = models.MeetingMinutes(
        fecha=fecha,
        status=estado,
        form_data=data,
    )
    db.add(new_minuta)
    db.commit()
    db.refresh(new_minuta)

    return RedirectResponse(url="/minutas", status_code=303)


@router.get("/minutas/{minuta_id}/editar", response_class=HTMLResponse)
async def editar_minuta(request: Request, minuta_id: int, db: Session = Depends(get_db)):
    minuta = db.query(models.MeetingMinutes).filter(models.MeetingMinutes.id == minuta_id).first()
    if not minuta:
        return RedirectResponse(url="/minutas", status_code=303)

    clientes = list_customers(db)
    return templates.TemplateResponse(request, 'nueva_minuta.html', {
        "request": request,
        "minuta": minuta,
        "form_data": minuta.form_data or {},
        "title": f"Editar Minuta #{minuta.id}",
        "action_url": f"/minutas/{minuta_id}/editar",
        "active_page": "minutas",
        "clientes": clientes,
    })


@router.post("/minutas/{minuta_id}/editar")
async def save_editar_minuta(minuta_id: int, request: Request, db: Session = Depends(get_db)):
    minuta = db.query(models.MeetingMinutes).filter(models.MeetingMinutes.id == minuta_id).first()
    if not minuta:
        return RedirectResponse(url="/minutas", status_code=303)

    form = await request.form()
    data = safe_json_loads(form.get("form_data"))

    minuta.fecha = data.get("fecha", "") or ""
    minuta.status = data.get("status", "Borrador")
    minuta.form_data = data
    minuta.updated_at = datetime.datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/minutas", status_code=303)


@router.post("/eliminar-minuta/{minuta_id}")
async def delete_minuta(minuta_id: int, request: Request, db: Session = Depends(get_db)):
    minuta = db.query(models.MeetingMinutes).filter(models.MeetingMinutes.id == minuta_id).first()
    if minuta:
        from services.trash_service import move_to_trash
        user = getattr(request.state, 'user', None)
        uid = int(user["sub"]) if user else None
        uname = user.get("username") if user else None
        fd = minuta.form_data or {}
        move_to_trash(db, "meeting_minutes", minuta.id, {
            "id": minuta.id,
            "fecha": minuta.fecha,
            "status": minuta.status,
            "form_data": fd,
        }, uid, uname, f"Minuta #{minuta.id}")
        db.delete(minuta)
        db.commit()
    return RedirectResponse(url="/minutas", status_code=303)
