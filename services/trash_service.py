"""Papelera (soft delete).

Design note: this used to *only* stamp ``restored_at`` and never re-insert the
row, so the "Restaurar" button lied to the user — the record was gone forever.
Deletion here is a real hard delete preceded by a JSON snapshot, so restoring
means re-inserting that snapshot. Each entity type has an explicit re-insertion
function below; anything without one is reported as non-restorable instead of
silently pretending to succeed.
"""

import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

import models


def _utcnow_naive() -> datetime.datetime:
    """Naive UTC timestamp, matching the DateTime columns in models.py."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def move_to_trash(
    db: Session,
    entity_type: str,
    entity_id: Optional[int],
    entity_data: dict,
    deleted_by_id: Optional[int] = None,
    deleted_by_name: Optional[str] = None,
    entity_name: Optional[str] = None,
):
    item = models.TrashItem(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        data=entity_data,
        deleted_by=deleted_by_id,
        deleted_by_name=deleted_by_name,
    )
    db.add(item)
    db.commit()
    return item


def list_trash(db: Session, entity_type: Optional[str] = None):
    query = db.query(models.TrashItem).filter(models.TrashItem.restored_at.is_(None))
    if entity_type:
        query = query.filter(models.TrashItem.entity_type == entity_type)
    return query.order_by(desc(models.TrashItem.deleted_at)).all()


# ── Re-insertion per entity type ────────────────────────────────────────────
def _restore_product(db: Session, data: dict):
    product = models.Product(
        name=data.get("name"),
        et_number=data.get("et_number"),
        material=data.get("material"),
        manufacturing_route=data.get("manufacturing_route"),
        dimensions_l=data.get("dimensions_l"),
        dimensions_a=data.get("dimensions_a"),
        dimensions_h=data.get("dimensions_h"),
        status=data.get("status"),
        is_active=data.get("is_active", True),
    )
    db.add(product)
    return product


def _restore_machine(db: Session, data: dict):
    serial = data.get("serial_number")
    if serial and db.query(models.Machine).filter(models.Machine.serial_number == serial).first():
        raise ValueError(f"Ya existe una máquina con el número de serie {serial}.")
    machine = models.Machine(
        serial_number=serial,
        model=data.get("model"),
        brand=data.get("brand"),
        plant_assigned=data.get("plant_assigned"),
        machine_type=data.get("machine_type"),
        line=data.get("line"),
        status=data.get("status"),
        customer_id=data.get("customer_id"),
        relevamiento_status=data.get("relevamiento_status", "Pendiente"),
        is_active=data.get("is_active", True),
    )
    db.add(machine)
    return machine


def _restore_assignment(db: Session, data: dict):
    assignment = models.ATAssignment(
        customer_name=data.get("customer_name"),
        technical_advisor=data.get("technical_advisor"),
        standard_visits=data.get("standard_visits", 0),
        premium_visits=data.get("premium_visits", 0),
        attention_required=data.get("attention_required", False),
        attention_observations=data.get("attention_observations"),
        status=data.get("status", "Activo"),
        valid_from=_utcnow_naive(),
        valid_to=None,
        is_active=True,
    )
    db.add(assignment)
    return assignment


def _restore_infrastructure(db: Session, data: dict):
    survey = models.InfrastructureSurvey(
        customer_id=data.get("customer_id"),
        plant=data.get("plant"),
        technical_advisor=data.get("technical_advisor"),
        status=data.get("status"),
        storage_data=data.get("storage_data") or {},
        packaging_data=data.get("packaging_data") or {},
        palletizing_data=data.get("palletizing_data") or {},
        logistics_data=data.get("logistics_data") or {},
        is_active=True,
    )
    db.add(survey)
    return survey


def _restore_survey2(db: Session, data: dict):
    survey = models.TechnicalSurveyV2(
        customer_id=data.get("customer_id"),
        machine_id=data.get("machine_id"),
        fecha=data.get("fecha"),
        status=data.get("status"),
        form_data=data.get("form_data") or {},
        is_active=True,
    )
    db.add(survey)
    return survey


def _restore_visit2(db: Session, data: dict):
    visit = models.TechnicalVisit2(
        fecha=data.get("fecha"),
        status=data.get("status"),
        form_data=data.get("form_data") or {},
        is_active=True,
    )
    db.add(visit)
    return visit


def _restore_meeting_minutes(db: Session, data: dict):
    minute = models.MeetingMinutes(
        fecha=data.get("fecha"),
        status=data.get("status"),
        form_data=data.get("form_data") or {},
        is_active=True,
    )
    db.add(minute)
    return minute


RESTORERS = {
    "product": _restore_product,
    "machine": _restore_machine,
    "assignment": _restore_assignment,
    "infrastructure": _restore_infrastructure,
    "survey2": _restore_survey2,
    "visit2": _restore_visit2,
    "meeting_minutes": _restore_meeting_minutes,
}


def can_restore(entity_type: str) -> bool:
    return entity_type in RESTORERS


def restore_from_trash(db: Session, trash_id: int, restored_by_id: int):
    """Re-insert the snapshotted record and mark the trash entry as restored.

    Returns ``(item, error)``. ``item`` is None when the entry does not exist;
    ``error`` carries a human-readable reason when restoration could not be done
    (for example, the natural key has been reused in the meantime), so the UI can
    report it honestly instead of claiming success.
    """
    item = db.query(models.TrashItem).filter(models.TrashItem.id == trash_id).first()
    if not item:
        return None, None

    if item.restored_at is not None:
        return item, "El elemento ya fue restaurado."

    restorer = RESTORERS.get(item.entity_type)
    if restorer is None:
        return item, (
            f"El tipo '{item.entity_type}' no admite restauración automática. "
            "Los datos originales siguen en la papelera."
        )

    try:
        restorer(db, item.data or {})
        item.restored_at = _utcnow_naive()
        item.restored_by = restored_by_id
        db.commit()
        return item, None
    except ValueError as exc:
        db.rollback()
        return item, str(exc)
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        return item, f"No se pudo restaurar: {exc}"


def permanently_delete_trash(db: Session, trash_id: int):
    item = db.query(models.TrashItem).filter(models.TrashItem.id == trash_id).first()
    if not item:
        return None
    db.delete(item)
    db.commit()
    return item


def permanently_delete_all_trash(db: Session, entity_type: Optional[str] = None):
    query = db.query(models.TrashItem).filter(models.TrashItem.restored_at.is_(None))
    if entity_type:
        query = query.filter(models.TrashItem.entity_type == entity_type)
    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return count
