"""Historial de cambios.

Registra quién cambió qué y cuándo. Dos decisiones que vale la pena conocer:

* **Se guardan las diferencias, no el registro entero.** Para mostrar qué se
  modificó alcanza con los campos que cambiaron; guardar el objeto completo
  duplicaría cada registro en cada edición.
* **Se guarda el nombre del usuario además de su id.** Si el usuario se elimina, el
  historial tiene que seguir siendo legible.

El registro nunca debe tumbar la operación que lo origina: si falla el historial,
el cambio del usuario igual se guarda. Por eso `registrar` no propaga excepciones.
"""

import datetime

import models

# Nombres legibles de cada entidad.
ETIQUETAS = {
    "customer": "Cliente",
    "machine": "Máquina",
    "visit": "Visita técnica",
    "minute": "Minuta",
    "product": "Producto",
    "at_assignment": "Asignación AT",
    "tracking": "Tarea de seguimiento",
}

ACCIONES = {
    "crear": "Creó",
    "editar": "Editó",
    "desactivar": "Desactivó",
    "reactivar": "Reactivó",
    "eliminar": "Eliminó",
}

# Campos que no aportan al historial: ruido técnico o datos que no se editan a mano.
IGNORAR = {
    "id", "updated_at", "created_at", "hashed_password",
    "inactivated_by_id", "inactivated_at",
}


def _legible(valor):
    """Convierte un valor a algo que se pueda mostrar en una frase."""
    if valor is None or valor == "":
        return "vacío"
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, (dict, list)):
        return f"({len(valor)} elemento{'s' if len(valor) != 1 else ''})"
    texto = str(valor)
    return texto if len(texto) <= 60 else texto[:57] + "…"


def diferencias(antes, despues):
    """Campos que cambiaron entre dos versiones de un registro.

    Devuelve ``{campo: {"antes": x, "despues": y}}`` con los valores ya
    convertidos a texto legible.
    """
    cambios = {}
    if not antes or not despues:
        return cambios
    for campo, valor_despues in despues.items():
        if campo in IGNORAR:
            continue
        valor_antes = antes.get(campo)
        # Se comparan los valores normalizados: cambiar "  " por "" no es un cambio.
        if isinstance(valor_antes, (dict, list)) or isinstance(valor_despues, (dict, list)):
            iguales = valor_antes == valor_despues
        else:
            # Los espacios sobrantes no son un cambio: pasar de "  " a "" es vaciar
            # el campo, no modificarlo. Sin esto el historial se llena de ruido.
            a = str(valor_antes if valor_antes is not None else "").strip()
            b = str(valor_despues if valor_despues is not None else "").strip()
            iguales = a == b
        if not iguales:
            cambios[campo] = {"antes": _legible(valor_antes),
                              "despues": _legible(valor_despues)}
    return cambios


def registrar(db, entity, entity_id, action, user=None, entity_label=None,
              changes=None, commit=True):
    """Anota un cambio. Nunca lanza: el historial no debe tumbar la operación."""
    try:
        usuario = None
        if user:
            # `user` puede ser el dict de la sesión o el modelo User.
            if isinstance(user, dict):
                usuario = user
            else:
                usuario = {"sub": user.id, "username": user.username}
        registro = models.ActivityLog(
            entity=entity,
            entity_id=entity_id,
            action=action,
            entity_label=(entity_label or "")[:200] or None,
            user_id=int(usuario["sub"]) if usuario and usuario.get("sub") else None,
            username=(usuario or {}).get("username"),
            changes=changes or None,
        )
        db.add(registro)
        if commit:
            db.commit()
        return registro
    except Exception:
        # Si falla el registro del historial, se revierte sólo eso y se sigue.
        try:
            db.rollback()
        except Exception:
            pass
        return None


def historial(db, entity, entity_id, limite=50):
    """Últimos cambios de un registro, del más reciente al más viejo."""
    return (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.entity == entity,
                models.ActivityLog.entity_id == entity_id)
        .order_by(models.ActivityLog.created_at.desc(),
                  models.ActivityLog.id.desc())
        .limit(limite)
        .all()
    )


def recientes(db, limite=100):
    """Últimos cambios de todo el sistema, para la vista global."""
    return (
        db.query(models.ActivityLog)
        .order_by(models.ActivityLog.created_at.desc(),
                  models.ActivityLog.id.desc())
        .limit(limite)
        .all()
    )


def resumen(registro):
    """Una frase que describe el cambio, para mostrar en la lista."""
    accion = ACCIONES.get(registro.action, registro.action)
    entidad = ETIQUETAS.get(registro.entity, registro.entity)
    objeto = registro.entity_label or f"#{registro.entity_id}"
    if registro.changes:
        campos = ", ".join(list(registro.changes.keys())[:4])
        return f"{accion} {entidad.lower()} «{objeto}» — {campos}"
    return f"{accion} {entidad.lower()} «{objeto}»"


def snapshot(objeto):
    """Copia de los campos de un registro, para poder comparar antes y después.

    Se arma desde las columnas del modelo, así sirve para cualquier entidad sin
    mantener una lista de campos por tabla que se desactualizaría.
    """
    if objeto is None:
        return {}
    datos = {}
    for columna in objeto.__table__.columns:
        datos[columna.name] = getattr(objeto, columna.name, None)
    return datos
