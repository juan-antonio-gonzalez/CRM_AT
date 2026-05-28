from sqlalchemy.orm import Session
from fastapi import HTTPException
import models


def list_assignments(db: Session):
    return db.query(models.ATAssignment).order_by(models.ATAssignment.customer_name).all()


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


def quick_create_assignment(db: Session, name: str, at: str = None):
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del cliente es obligatorio")
    existing = db.query(models.ATAssignment).filter(models.ATAssignment.customer_name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe una asignación para '{name}'")
    new_assignment = models.ATAssignment(
        customer_name=name, technical_advisor=at, standard_visits=0, premium_visits=0
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return new_assignment


def update_assignment_kpis(db: Session, assignment_id: int, data: dict):
    assignment = db.query(models.ATAssignment).filter(models.ATAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")

    standard = data.get("standard")
    premium = data.get("premium")
    at_name = data.get("at")
    name = data.get("name")

    if standard is not None:
        assignment.standard_visits = int(standard)
    if premium is not None:
        assignment.premium_visits = int(premium)
    if at_name is not None:
        assignment.technical_advisor = at_name
    if name is not None:
        if name != assignment.customer_name:
            existing = db.query(models.ATAssignment).filter(models.ATAssignment.customer_name == name).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Ya existe una asignación para '{name}'")
        assignment.customer_name = name
    if "attention_required" in data:
        assignment.attention_required = bool(data.get("attention_required"))
    if "attention_observations" in data:
        assignment.attention_observations = data.get("attention_observations")

    db.commit()
    return {"status": "success", "message": "Registro actualizado"}


def delete_assignment(db: Session, assignment_id: int, user_id: int = None, username: str = None):
    assignment = db.query(models.ATAssignment).filter(models.ATAssignment.id == assignment_id).first()
    if assignment:
        from services.trash_service import move_to_trash
        move_to_trash(db, "assignment", assignment_id, {
            "customer_name": assignment.customer_name,
            "technical_advisor": assignment.technical_advisor,
            "standard_visits": assignment.standard_visits,
            "premium_visits": assignment.premium_visits,
            "attention_required": assignment.attention_required,
            "attention_observations": assignment.attention_observations,
        }, user_id, username, assignment.customer_name)
        db.delete(assignment)
        db.commit()
