from fastapi import HTTPException
from sqlalchemy.orm import Session
import datetime


def soft_deactivate(
    db: Session,
    model,
    record_id: int,
    reason: str,
    user_id: int = None,
):
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="Debe indicar el motivo de la desactivación")

    record = db.query(model).filter(model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    if not hasattr(record, 'is_active'):
        raise HTTPException(status_code=400, detail="Este registro no soporta desactivación")

    if not record.is_active:
        raise HTTPException(status_code=400, detail="El registro ya está inactivo")

    record.is_active = False
    record.inactivation_reason = reason.strip()
    record.inactivated_by_id = user_id
    record.inactivated_at = datetime.datetime.utcnow()
    db.commit()
    return {"status": "success", "message": "Registro desactivado"}


def soft_reactivate(
    db: Session,
    model,
    record_id: int,
):
    record = db.query(model).filter(model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    if not hasattr(record, 'is_active'):
        raise HTTPException(status_code=400, detail="Este registro no soporta reactivación")

    if record.is_active:
        raise HTTPException(status_code=400, detail="El registro ya está activo")

    record.is_active = True
    record.inactivation_reason = None
    record.inactivated_by_id = None
    record.inactivated_at = None
    db.commit()
    return {"status": "success", "message": "Registro reactivado"}
