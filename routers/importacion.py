"""Importación masiva desde Excel.

Flujo en tres pasos, pensado para que nunca se escriba a ciegas sobre datos reales:

    GET  /importar              elegir qué importar y subir el archivo
    POST /importar/previsualizar  validar y mostrar qué se va a cargar y qué no
    POST /importar/confirmar      escribir en la base

Entre la previsualización y la confirmación no se vuelve a subir el archivo: se
guarda en un temporal con un token y se relee al confirmar. Al confirmar se
**revalida** contra la base, porque entre un paso y otro pudo cargarse algo.
"""

import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

import models
from database import get_db
from services import importacion
from templating import templates

router = APIRouter(tags=["importacion"])

# Los temporales viven fuera del árbol servido: nunca deben ser accesibles por URL.
DIR_TEMP = os.path.join(tempfile.gettempdir(), "crm-at-import")
MAX_BYTES = 8 * 1024 * 1024  # 8 MB alcanza para decenas de miles de filas


def _ruta_temp(token: str) -> str:
    # El token es un uuid generado acá, pero se valida igual: nunca se arma una
    # ruta con algo que venga del formulario sin comprobarlo.
    try:
        uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        return ""
    return os.path.join(DIR_TEMP, f"{token}.xlsx")


@router.get("/importar", response_class=HTMLResponse)
async def importar_inicio(request: Request, tipo: str = "clientes", ok: int = None,
                          fallas: int = None):
    return templates.TemplateResponse(request, "importar.html", {
        "request": request,
        "active_page": "importar",
        "tipo": tipo if tipo in importacion.TIPOS else "clientes",
        "tipos": {k: v["titulo"] for k, v in importacion.TIPOS.items()},
        "columnas": importacion.TIPOS.get(tipo, importacion.CLIENTES)["columnas"],
        "filas": None,
        "errores": None,
        "token": None,
        "cargados": ok,
        "fallados": fallas,
    })


@router.get("/importar/plantilla/{tipo}")
async def importar_plantilla(tipo: str):
    """Descarga una planilla vacía con los encabezados correctos."""
    respuesta = importacion.plantilla(tipo)
    if respuesta is None:
        return RedirectResponse("/importar", status_code=303)
    return respuesta


@router.post("/importar/previsualizar", response_class=HTMLResponse)
async def importar_previsualizar(
    request: Request,
    tipo: str = Form("clientes"),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Lee el archivo y muestra qué se importaría, sin escribir nada."""
    tipo = tipo if tipo in importacion.TIPOS else "clientes"

    contenido = await archivo.read()
    contexto = {
        "request": request, "active_page": "importar", "tipo": tipo,
        "tipos": {k: v["titulo"] for k, v in importacion.TIPOS.items()},
        "columnas": importacion.TIPOS[tipo]["columnas"],
        "filas": None, "errores": None, "token": None,
        "cargados": None, "fallados": None,
    }

    if not contenido:
        contexto["error_archivo"] = "No se recibió ningún archivo."
        return templates.TemplateResponse(request, "importar.html", contexto)
    if len(contenido) > MAX_BYTES:
        contexto["error_archivo"] = "El archivo supera los 8 MB."
        return templates.TemplateResponse(request, "importar.html", contexto)

    filas, error = importacion.leer_planilla(contenido, tipo)
    if error:
        contexto["error_archivo"] = error
        return templates.TemplateResponse(request, "importar.html", contexto)

    listas, errores = importacion.validar(db, tipo, filas)

    # El archivo se guarda para el paso de confirmación: los navegadores no
    # permiten precargar un input de archivo, así que no se puede reenviar.
    os.makedirs(DIR_TEMP, exist_ok=True)
    token = str(uuid.uuid4())
    with open(_ruta_temp(token), "wb") as fh:
        fh.write(contenido)

    contexto.update({
        "filas": listas,
        "errores": errores,
        "token": token,
        "total": len(filas),
        "nombre_archivo": archivo.filename,
    })
    return templates.TemplateResponse(request, "importar.html", contexto)


@router.post("/importar/confirmar", response_class=HTMLResponse)
async def importar_confirmar(
    request: Request,
    tipo: str = Form("clientes"),
    token: str = Form(""),
    db: Session = Depends(get_db),
):
    """Escribe en la base lo que se previsualizó."""
    tipo = tipo if tipo in importacion.TIPOS else "clientes"
    ruta = _ruta_temp(token)

    if not ruta or not os.path.exists(ruta):
        return RedirectResponse("/importar?tipo=" + tipo, status_code=303)

    try:
        with open(ruta, "rb") as fh:
            contenido = fh.read()
    finally:
        # El temporal se borra siempre, incluso si falla la importación.
        try:
            os.remove(ruta)
        except OSError:
            pass

    filas, error = importacion.leer_planilla(contenido, tipo)
    if error:
        return RedirectResponse("/importar?tipo=" + tipo, status_code=303)

    creados, _omitidos, _errores = importacion.importar(db, tipo, filas)

    destino = f"/importar?tipo={tipo}&ok={creados}"
    return RedirectResponse(destino, status_code=303)
