from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from services import trash_service
from security import get_current_user
import models

router = APIRouter(tags=["trash"])
templates = Jinja2Templates(directory="templates")


def require_admin(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")


@router.get("/papelera", response_class=HTMLResponse)
async def trash_view(request: Request, tipo: Optional[str] = Query(None), db: Session = Depends(get_db)):
    require_admin(request)
    items = trash_service.list_trash(db, tipo)
    return templates.TemplateResponse("trash.html", {
        "request": request,
        "items": items,
        "active_tipo": tipo,
        "active_page": "papelera"
    })


@router.post("/papelera/restaurar/{trash_id}")
async def restore_item(trash_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    item = trash_service.restore_from_trash(db, trash_id, int(user["sub"]))
    if not item:
        raise HTTPException(status_code=404, detail="Elemento no encontrado en la papelera")

    return RedirectResponse(url="/papelera", status_code=303)


@router.get("/papelera/detalle/{trash_id}", response_class=JSONResponse)
async def trash_detail(trash_id: int, db: Session = Depends(get_db)):
    item = db.query(models.TrashItem).filter(models.TrashItem.id == trash_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    return {"data": item.data}
