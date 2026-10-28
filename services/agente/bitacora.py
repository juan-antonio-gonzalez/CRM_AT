"""Auditoría de las consultas a Caty.

Se registra en `activity_log`, la tabla de actividad del sistema, que ya existe.
Cuando un cliente discuta un dato, hay que poder saber qué le dijo Caty y cuándo.

Tres decisiones
---------------
**No se guarda el system prompt ni la base de conocimiento.** Un volcado de
`activity_log` no puede exponer las instrucciones del sistema: es exactamente el
material que un atacante quiere, y guardarlo en una tabla que se consulta desde la
interfaz sería regalarlo.

**Nunca propaga excepciones.** La auditoría no puede tumbar una consulta que el
usuario ya vio respondida. Es el mismo criterio que `services/auditoria.py`.

**Sesión propia y corta.** El registro ocurre cuando el stream termina, y ahí la
sesión del request ya no es confiable: `get_db` se cierra al finalizar la
respuesta. Se abre una sesión nueva sólo para el insert.

Lo que sí importa de un rechazo
-------------------------------
Se guarda el motivo, así que las consultas rechazadas y las que no supieron
responder quedan separadas de las que salieron bien. Esa lista es la de lo que
falta documentar.
"""

from __future__ import annotations

import logging

import models
from database import SessionLocal
from services import auditoria

logger = logging.getLogger(__name__)

# `entity_label` es String(200) en el modelo: la pregunta se recorta al ancho de
# la columna. `auditoria.registrar` también recorta, pero no se depende de eso:
# que el dato entre en la columna es responsabilidad de quien lo arma.
MAX_PREGUNTA = 200

# Tope del texto de la respuesta guardado. El modelo está acotado a 2500
# caracteres, así que en la práctica no recorta nada; está para que una respuesta
# anómala no llene la tabla.
MAX_RESPUESTA = 4000


def registrar_consulta(
    *,
    usuario: dict | None,
    pregunta: str,
    respuesta: str = "",
    motivo: str = "ok",
    ruta: str = "",
    tema: str = "",
    pantalla: dict | None = None,
) -> bool:
    """Anota una consulta. Devuelve si se pudo guardar. Nunca lanza."""
    try:
        db = SessionLocal()
    except Exception as exc:
        logger.warning("No se pudo abrir sesión para auditar: %s", exc)
        return False

    try:
        auditoria.registrar(
            db,
            entity="agente",
            # La columna no acepta nulos y una consulta no tiene id de registro:
            # el 0 es explícito y no colisiona con ninguna entidad real.
            entity_id=0,
            action="consultar",
            user=usuario,
            entity_label=(pregunta or "").strip()[:MAX_PREGUNTA],
            changes={
                "pregunta": (pregunta or "")[:1000],
                "respuesta": (respuesta or "")[:MAX_RESPUESTA],
                "motivo": motivo,
                "ruta": ruta or None,
                "tema": tema or None,
                "pantalla": (pantalla or {}).get("ruta") if pantalla else None,
            },
        )
        return True
    except Exception as exc:
        logger.warning("No se pudo auditar la consulta: %s", exc)
        return False
    finally:
        try:
            db.close()
        except Exception:
            pass


def consultas(db, usuario_id: int | None = None, limite: int = 50):
    """Últimas consultas registradas, para revisarlas."""
    consulta = db.query(models.ActivityLog).filter(
        models.ActivityLog.entity == "agente")
    if usuario_id is not None:
        consulta = consulta.filter(models.ActivityLog.user_id == usuario_id)
    return (
        consulta.order_by(models.ActivityLog.created_at.desc(),
                          models.ActivityLog.id.desc())
        .limit(limite)
        .all()
    )
