import datetime
from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models


def list_assignments(db: Session, vigentes_only: bool = False):
    q = db.query(models.ATAssignment)
    if vigentes_only:
        q = q.filter(
            or_(models.ATAssignment.valid_to.is_(None), models.ATAssignment.valid_to > datetime.datetime.utcnow())
        )
    return q.order_by(models.ATAssignment.customer_name).all()


def get_available_customers(db: Session):
    unique_customer_names = db.query(models.Customer.name).distinct().all()
    return [c[0] for c in unique_customer_names if c[0]]


def get_advisor_names(db: Session):
    return [a.name for a in db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()]


def build_table_data(assignments: list):
    table_data = []
    grand_total_estandar = 0
    grand_total_premium = 0
    for a in assignments:
        table_data.append({
            "id": a.id,
            "cliente": a.customer_name,
            "planta": a.plant or "—",
            "at": a.technical_advisor or "No asignado",
            "estandar": a.standard_visits or 0,
            "premium": a.premium_visits or 0,
            "total": (a.standard_visits or 0) + (a.premium_visits or 0),
            "attention_required": getattr(a, 'attention_required', False),
            "attention_observations": getattr(a, 'attention_observations', "")
        })
        grand_total_estandar += (a.standard_visits or 0)
        grand_total_premium += (a.premium_visits or 0)
    return table_data, grand_total_estandar, grand_total_premium


def quick_create_assignment(db: Session, name: str, at: str = None, status: str = "Activo",
                            valid_from: str = None, valid_to: str = None, plant: str = None):
    import datetime
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del cliente es obligatorio")
    if not plant:
        raise HTTPException(
            status_code=400,
            detail="Hay que indicar la planta: una asignación es de una planta, no del cliente entero",
        )
    # El duplicado se busca por cliente **y planta**. Antes era sólo por nombre, así
    # que un cliente con dos plantas no podía tener una asignación en cada una.
    existing = db.query(models.ATAssignment).filter(
        models.ATAssignment.customer_name == name,
        models.ATAssignment.plant == plant,
        or_(models.ATAssignment.valid_to.is_(None), models.ATAssignment.valid_to > datetime.datetime.utcnow())
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una asignación vigente para '{name}' en la planta '{plant}'",
        )

    vf = datetime.datetime.utcnow()
    if valid_from:
        try:
            vf = datetime.datetime.fromisoformat(valid_from.replace('T', ' ') if 'T' in valid_from else valid_from)
        except Exception:
            pass

    vt = None
    if valid_to:
        try:
            vt = datetime.datetime.fromisoformat(valid_to.replace('T', ' ') if 'T' in valid_to else valid_to)
        except Exception:
            pass

    new_assignment = models.ATAssignment(
        customer_name=name, plant=plant, technical_advisor=at,
        standard_visits=0, premium_visits=0,
        status=status, valid_from=vf, valid_to=vt
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return new_assignment


def _parse_dt(val):
    if not val:
        return None
    try:
        return datetime.datetime.fromisoformat(val.replace('T', ' ') if 'T' in val else val)
    except Exception:
        return None

def _end_of_day(dt):
    if dt and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        return dt.replace(hour=23, minute=59, second=59)
    return dt


def update_assignment_kpis(db: Session, assignment_id: int, data: dict):
    assignment = db.query(models.ATAssignment).filter(models.ATAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")

    standard = data.get("standard_visits")
    premium = data.get("premium_visits")
    at_name = data.get("at")
    name = data.get("name")
    status_val = data.get("status")
    valid_from_raw = data.get("valid_from")
    valid_to_raw = data.get("valid_to")

    now = datetime.datetime.utcnow()

    # Versioning policy. Creating an assignment and then filling in its values is
    # a two-request flow (POST /quick-create, then POST /update-kpis), so that
    # second call must fill in place rather than open a new version. That used to
    # be inferred from "was this row created less than 30 seconds ago?", which is
    # fragile: a slow user or a system clock skew silently produced a duplicate
    # version. The client can now declare its intent with ``reason`` /
    # ``created_now``; the heuristic remains only as a fallback for callers that
    # have not been updated yet.
    reason = (data.get("reason") or "").lower()
    if reason in ("create", "created", "fill"):
        is_initial_fill = True
    elif reason in ("edit", "update", "version"):
        is_initial_fill = False
    else:
        is_initial_fill = bool(assignment.valid_from) and \
            (now - assignment.valid_from).total_seconds() < 30

    if not is_initial_fill:
        # Recording a change must not silently invent a date: a typo previously
        # fell back to "now" and closed the current period without warning.
        new_vf = _parse_dt(valid_from_raw)
        if valid_from_raw and new_vf is None:
            raise HTTPException(
                status_code=400,
                detail="La fecha 'válido desde' no es válida. Usá el formato AAAA-MM-DD.",
            )
        new_vf = new_vf or now
        new_vt = _end_of_day(_parse_dt(valid_to_raw))
        if valid_to_raw and new_vt is None:
            raise HTTPException(
                status_code=400,
                detail="La fecha 'válido hasta' no es válida. Usá el formato AAAA-MM-DD.",
            )
        assignment.valid_to = new_vf
        db.flush()
        new_assignment = models.ATAssignment(
            customer_name=name or assignment.customer_name,
            # La versión nueva sigue siendo de la misma planta. Sin esto, cerrar un
            # período y abrir el siguiente perdería la planta y la asignación
            # volvería a valer para todas.
            plant=data.get("plant") or assignment.plant,
            technical_advisor=at_name or assignment.technical_advisor,
            standard_visits=int(standard) if standard is not None else (assignment.standard_visits or 0),
            premium_visits=int(premium) if premium is not None else (assignment.premium_visits or 0),
            status=status_val or assignment.status,
            valid_from=new_vf,
            valid_to=new_vt,
            attention_required=data.get("attention_required", assignment.attention_required),
            attention_observations=data.get("attention_observations", assignment.attention_observations),
        )
        db.add(new_assignment)
        db.commit()
        return {"status": "success", "message": "Nueva versión creada", "id": new_assignment.id}
    else:
        if standard is not None:
            assignment.standard_visits = int(standard)
        if premium is not None:
            assignment.premium_visits = int(premium)
        if at_name is not None:
            assignment.technical_advisor = at_name
        if name is not None:
            if name != assignment.customer_name:
                existing = db.query(models.ATAssignment).filter(
                    models.ATAssignment.customer_name == name,
                    models.ATAssignment.plant == assignment.plant,
                    models.ATAssignment.valid_to.is_(None)
                ).first()
                if existing:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Ya existe una asignación para '{name}' en esa planta",
                    )
            assignment.customer_name = name
        if data.get("plant") is not None:
            assignment.plant = data.get("plant") or None
        vf = _parse_dt(valid_from_raw)
        if vf:
            assignment.valid_from = vf
        vt = _end_of_day(_parse_dt(valid_to_raw))
        assignment.valid_to = vt
        if "attention_required" in data:
            assignment.attention_required = bool(data.get("attention_required"))
        if "attention_observations" in data:
            assignment.attention_observations = data.get("attention_observations")
        if status_val is not None:
            assignment.status = status_val
        db.commit()
        return {"status": "success", "message": "Registro actualizado"}


def delete_assignment(db: Session, assignment_id: int, user_id: int = None, username: str = None):
    assignment = db.query(models.ATAssignment).filter(models.ATAssignment.id == assignment_id).first()
    if assignment:
        assignment.valid_to = datetime.datetime.utcnow()
        from services.trash_service import move_to_trash
        move_to_trash(db, "assignment", assignment_id, {
            "customer_name": assignment.customer_name,
            "technical_advisor": assignment.technical_advisor,
            "standard_visits": assignment.standard_visits,
            "premium_visits": assignment.premium_visits,
            "attention_required": assignment.attention_required,
            "attention_observations": assignment.attention_observations,
        }, user_id, username, assignment.customer_name)
        db.commit()
