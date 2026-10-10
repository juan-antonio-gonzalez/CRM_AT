from urllib.parse import quote

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from logger import get_logger
from services import trash_service
from security import get_current_user
import models
from templating import templates

logger = get_logger(__name__)

router = APIRouter(tags=["trash"])


def require_admin(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")


@router.get("/papelera", response_class=HTMLResponse)
async def trash_view(request: Request, tipo: Optional[str] = Query(None),
                     db: Session = Depends(get_db)):
    require_admin(request)
    items = trash_service.list_trash(db, tipo)
    return templates.TemplateResponse(request, 'trash.html', {
        "request": request,
        "items": items,
        "active_tipo": tipo,
        "active_page": "papelera",
    })


@router.post("/papelera/restaurar/{trash_id}")
async def restore_item(trash_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    item, error = trash_service.restore_from_trash(db, trash_id, int(user["sub"]))
    if not item:
        raise HTTPException(status_code=404, detail="Elemento no encontrado en la papelera")
    if error:
        logger.warning("Restauracion fallida de trash_id=%s: %s", trash_id, error)
        return RedirectResponse(url=f"/papelera?error={quote(error)}", status_code=303)
    return RedirectResponse(url="/papelera?success=restaurado", status_code=303)


@router.post("/papelera/eliminar/{trash_id}")
async def permanently_delete_item(trash_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    item = trash_service.permanently_delete_trash(db, trash_id)
    if not item:
        raise HTTPException(status_code=404, detail="Elemento no encontrado en la papelera")
    return RedirectResponse(url="/papelera?success=eliminado", status_code=303)


@router.post("/papelera/vaciar")
async def empty_trash(request: Request, tipo: Optional[str] = Query(None), db: Session = Depends(get_db)):
    require_admin(request)
    count = trash_service.permanently_delete_all_trash(db, tipo)
    logger.info("Papelera vaciada: %s elementos (tipo=%s)", count, tipo or "todos")
    return RedirectResponse(url="/papelera" + (f"?tipo={tipo}" if tipo else ""), status_code=303)


@router.get("/papelera/detalle/{trash_id}", response_class=JSONResponse)
async def trash_detail(trash_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    item = db.query(models.TrashItem).filter(models.TrashItem.id == trash_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    return {"data": item.data}
