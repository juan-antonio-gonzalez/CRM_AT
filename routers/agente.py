"""Endpoints de Caty, la instructora de uso.

Dos decisiones que conviene conocer
-----------------------------------
**El cuerpo va como formulario, no como JSON.** El middleware de ``main.py``
valida el CSRF sólo cuando el cuerpo es ``form-urlencoded`` o ``multipart``; un
endpoint que reciba JSON no pasa por esa validación y queda sin protección. En
vez de reimplementar la comprobación acá —con la chance de equivocarse—, el
endpoint usa el mismo formato que el resto de la aplicación y hereda la
validación que ya existe y ya está cubierta por ``tests/test_csrf.py``. La
comprobación del middleware falla cerrada, que es lo que se quiere.

**La ruta va bajo ``/api/``.** El middleware responde 401 y 403 en JSON para los
caminos que empiezan con ``/api/``, en vez de redirigir al login con un 303. Para
una llamada de ``fetch`` es la diferencia entre un error que el widget puede
mostrar y una página de login metida dentro del modal.

El historial viaja como un texto JSON dentro del formulario. Es menos elegante que
un cuerpo anidado, pero el formato es el precio de heredar el CSRF.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from config import settings
from services.agente import bitacora, chat, persona

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agente"])

# Tope defensivo: el historial lo manda el navegador y no tiene por qué ser
# grande. Más que esto se descarta en silencio.
MAX_HISTORIAL = 20


def _sse(evento: chat.Evento) -> str:
    """Un evento en el formato que espera EventSource/fetch."""
    datos = json.dumps(evento.datos, ensure_ascii=False)
    return f"event: {evento.tipo}\ndata: {datos}\n\n"


def _leer_historial(crudo: str) -> list[dict]:
    if not crudo:
        return []
    try:
        datos = json.loads(crudo)
    except (ValueError, TypeError):
        return []
    if not isinstance(datos, list):
        return []
    limpio: list[dict] = []
    for turno in datos[-MAX_HISTORIAL:]:
        if isinstance(turno, dict) and isinstance(turno.get("texto"), str):
            limpio.append({
                "rol": "assistant" if turno.get("rol") == "assistant" else "user",
                "texto": turno["texto"][: settings.agente_max_entrada],
            })
    return limpio


def _ocultos(request) -> list:
    """Las pantallas que este usuario no ve, para que Caty no lo mande ahí.

    `/api/agente/` es una ruta libre, así que el middleware no carga el usuario: se
    busca acá. Y si la base no responde, se devuelve una lista vacía y Caty
    contesta igual —los endpoints de Caty **no dependen de la base a propósito**, y
    esta consulta no puede cambiar eso—.

    Ojo con el caso «no se pudo leer el usuario»: devolver los módulos de un usuario
    inexistente daría el conjunto vacío, o sea *todas* las pantallas ocultas, y
    Caty le diría a todo el mundo que no tiene acceso a nada.
    """
    try:
        from database import SessionLocal
        from models import User
        from services import permisos

        usuario = getattr(request.state, "db_user", None)
        if usuario is None:
            datos = getattr(request.state, "user", None)
            if not datos:
                return []
            db = SessionLocal()
            try:
                usuario = db.query(User).filter(User.id == int(datos["sub"])).first()
            finally:
                db.close()
        if usuario is None:
            return []

        vistas = permisos.visibles(usuario)
        return [m.etiqueta for m in permisos.MODULOS
                if m.clave not in vistas and not m.solo_admin]
    except Exception:
        return []


@router.get("/api/agente/estado")
async def estado():
    """El widget consulta esto al cargar.

    Permite desplegar con Caty apagada y que la interfaz simplemente no muestre el
    botón, en vez de ofrecer un modal que no responde.
    """
    return {
        "habilitado": settings.agente_habilitado,
        "nombre": persona.NOMBRE,
    }


@router.post("/api/agente/chat")
async def conversar(request: Request):
    if not settings.agente_habilitado:
        return JSONResponse(
            status_code=503,
            content={"motivo": "deshabilitada", "mensaje": persona.DESHABILITADA},
        )

    # El middleware ya leyó y cacheó el cuerpo para validar el CSRF, así que
    # `form()` lo vuelve a leer sin problema.
    formulario = await request.form()
    mensaje = str(formulario.get("mensaje", ""))
    ruta_actual = str(formulario.get("ruta_actual", ""))
    historial = _leer_historial(str(formulario.get("historial", "")))

    usuario = getattr(request.state, "user", None) or {}
    try:
        usuario_id = int(usuario.get("sub"))
    except (TypeError, ValueError):
        usuario_id = None

    async def flujo() -> AsyncIterator[str]:
        # Se acumula el desenlace mientras el stream sale, para poder auditarlo
        # al final. `fin`, `reemplazo` y `rechazo` traen el texto definitivo.
        motivo, respuesta, tema, pantalla = "ok", "", "", None
        try:
            async for evento in chat.responder(mensaje, historial, ruta_actual,
                                               usuario_id=usuario_id,
                                               modulos_ocultos=_ocultos(request)):
                if evento.tipo in ("fin", "reemplazo", "rechazo"):
                    respuesta = evento.datos.get("texto") or respuesta
                    motivo = evento.datos.get("motivo", motivo)
                    tema = evento.datos.get("tema") or tema
                    pantalla = evento.datos.get("pantalla") or pantalla
                elif evento.tipo == "error":
                    respuesta = evento.datos.get("mensaje", "")
                    motivo = evento.datos.get("motivo", "error")
                yield _sse(evento)
        except Exception:
            # Una excepción acá ya no se puede convertir en un código de estado:
            # la respuesta empezó a salir. Se avisa por el stream y se registra.
            logger.exception("Fallo el stream de Caty para %s",
                             usuario.get("username"))
            motivo = "interno"
            respuesta = persona.ERROR_SERVICIO
            yield _sse(chat.Evento("error", {
                "motivo": "interno",
                "mensaje": persona.ERROR_SERVICIO,
            }))
        finally:
            # En `finally` y no al final del `try`: si el usuario cierra la
            # pestaña a mitad de la respuesta, la consulta igual queda registrada.
            # Es justo el caso que interesa auditar.
            #
            # Va a un hilo porque el driver de PostgreSQL es sincrónico y bloquear
            # el event loop por un insert frenaría todos los demás streams.
            await run_in_threadpool(
                bitacora.registrar_consulta,
                usuario=usuario,
                pregunta=mensaje,
                respuesta=respuesta,
                motivo=motivo,
                ruta=ruta_actual,
                tema=tema,
                pantalla=pantalla,
            )

    return StreamingResponse(
        flujo(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx bufferea las respuestas por defecto, y una respuesta
            # bufferada no llega hasta que termina: el streaming se perdería y el
            # usuario vería el texto de golpe al final.
            "X-Accel-Buffering": "no",
        },
    )
