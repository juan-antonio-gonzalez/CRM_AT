"""Búsqueda transversal.

Una sola caja en la barra superior que cruza clientes, visitas, máquinas y minutas.
Antes había que entrar a cada módulo por separado y repetir la búsqueda.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import get_db
from services import busqueda as servicio
from templating import templates

router = APIRouter(tags=["busqueda"])


@router.get("/buscar", response_class=HTMLResponse)
async def buscar(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    grupos, total = servicio.buscar(db, q)
    return templates.TemplateResponse(request, "buscar.html", {
        "request": request,
        "active_page": "buscar",
        "q": q,
        "grupos": grupos,
        "total": total,
        "consultado": bool((q or "").strip()),
    })
