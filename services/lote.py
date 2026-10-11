"""Acciones en lote.

Desactivar veinte registros de a uno, con su motivo cada vez, es la clase de tarea
que hace que la gente deje de usar la herramienta.

La lógica vive acá y no en cada router: clientes, máquinas y productos se comportan
igual, y tener tres copias del mismo bucle garantizaba que se separaran con el
tiempo. Cada router sólo dice qué modelo, cómo se llama un registro y cómo se
obtiene su etiqueta.
"""

from fastapi import HTTPException

from services import auditoria, soft_delete as sd

# Tope de identificadores por petición: evita que un error recorra la tabla entera.
MAX_LOTE = 500

ACCIONES = ("desactivar", "reactivar")


def _error(mensaje, codigo=400):
    """Los endpoints de lote hablan JSON, así que sus errores también."""
    return {"mensaje": mensaje, "codigo": codigo}


def validar_peticion(ids, accion, motivo, user):
    """Comprueba la petición antes de tocar nada.

    Devuelve (ids_limpios, error). Se valida todo de entrada: es mejor decir una vez
    «falta el motivo» que devolver veinte filas omitidas por el mismo error.
    """
    if accion not in ACCIONES:
        return [], _error("Acción no válida")
    if not ids:
        return [], _error("No se seleccionó ningún registro")

    try:
        limpios = [int(i) for i in ids][:MAX_LOTE]
    except (TypeError, ValueError):
        return [], _error("Identificadores no válidos")

    rol = (user.get("role") or "") if user else ""
    if accion == "reactivar" and rol != "admin":
        return [], _error("Solo el admin puede reactivar", 403)
    # La desactivación individual ya exige el motivo; el lote tiene que ser
    # consistente con eso.
    if accion == "desactivar" and not (motivo or "").strip():
        return [], _error("Indicá el motivo de la desactivación")

    return limpios, None


def aplicar(db, modelo, ids, accion, motivo, user, etiqueta=None, registrar=None):
    """Aplica la acción a cada registro.

    `etiqueta` recibe el registro y devuelve cómo nombrarlo en el historial.
    `registrar` es el nombre de la entidad para el historial (por ejemplo
    "machine"); si no se pasa, no se registra.

    Devuelve (aplicados, omitidos). Nunca lanza por un registro que falla: se anota
    el motivo y se sigue con los demás.
    """
    uid = int(user["sub"]) if user and user.get("sub") else None
    aplicados, omitidos = 0, []

    for rid in ids:
        registro = db.query(modelo).filter(modelo.id == rid).first()
        if not registro:
            omitidos.append({"id": rid, "motivo": "no existe"})
            continue

        esta_activo = getattr(registro, "is_active", True)
        if accion == "desactivar" and not esta_activo:
            omitidos.append({"id": rid, "motivo": f"{etiqueta(registro)}: ya estaba inactivo"})
            continue
        if accion == "reactivar" and esta_activo:
            omitidos.append({"id": rid, "motivo": f"{etiqueta(registro)}: ya estaba activo"})
            continue

        try:
            if accion == "desactivar":
                sd.soft_deactivate(db, modelo, rid, motivo, uid)
            else:
                sd.soft_reactivate(db, modelo, rid)
            aplicados += 1
            if registrar:
                auditoria.registrar(
                    db, registrar, rid, accion, user=user, entity_label=etiqueta(registro),
                    changes=({"motivo": {"antes": "", "despues": motivo}}
                             if accion == "desactivar" else None),
                    commit=False)
        except HTTPException as ex:
            omitidos.append({"id": rid, "motivo": str(ex.detail)[:120]})
        except Exception as ex:
            omitidos.append({"id": rid, "motivo": str(ex)[:120]})

    # Los registros del historial se acumulan sin confirmar; los `soft_*` confirman
    # por su cuenta, pero el último quedaría sin guardar.
    try:
        db.commit()
    except Exception:
        db.rollback()

    return aplicados, omitidos
