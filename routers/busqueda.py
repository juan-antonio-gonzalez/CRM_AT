"""Búsqueda transversal.

Una sola caja en la barra superior que cruza clientes, visitas, máquinas y minutas.
Antes había que entrar a cada módulo por separado y repetir la búsqueda.
"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from services import busqueda as servicio
from templating import templates

router = APIRouter(tags=["busqueda"])


@router.get("/search")
async def search_heredado(q: str = Query("")):
    """La dirección vieja del buscador, redirigida al actual.

    `/search` renderizaba `layout.html` —la plantilla base, sin contenido— con los
    resultados ya calculados y descartados: la búsqueda de verdad vive en
    `/buscar`. Además del código muerto, dejar la dirección devolviendo una página
    en blanco es peor que redirigirla.

    Se mantiene como redirección permanente y no se elimina para que un enlace
    guardado o un marcador no terminen en un 404.
    """
    destino = "/buscar" + (f"?q={quote(q)}" if q else "")
    return RedirectResponse(url=destino, status_code=308)


@router.get("/buscar", response_class=HTMLResponse)
async def buscar(request: Request, q: str = Query(""), db: Session = Depends(get_db)):
    # Lo que se busca depende de lo que el usuario puede ver: un resultado que
    # lleva a un 403 es peor que no mostrarlo.
    from services import permisos
    visibles = permisos.visibles(getattr(request.state, "db_user", None))
    grupos, total = servicio.buscar(db, q, visibles)
    return templates.TemplateResponse(request, "buscar.html", {
        "request": request,
        "active_page": "buscar",
        "q": q,
        "grupos": grupos,
        "total": total,
        "consultado": bool((q or "").strip()),
    })
