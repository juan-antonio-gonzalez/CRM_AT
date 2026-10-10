import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
import models
from enums import RelevamientoStatus, CustomerStatus
from utils import calculate_relevo_status


def list_customers(db: Session, q: str = None, include_inactive: bool = False):
    """List customers.

    ``include_inactive`` defaults to False because this helper feeds the
    customer selectors in the visit/minute/survey forms — a soft-deleted
    customer must not be selectable there. Administrative views (organigrama,
    papelera) pass True explicitly.
    """
    query = db.query(models.Customer)
    if not include_inactive:
        query = query.filter(models.Customer.is_active.is_(True))
    if q:
        query = query.filter(
            (models.Customer.name.ilike(f"%{q}%")) |
            (models.Customer.plant.ilike(f"%{q}%")) |
            (models.Customer.industry_sector.ilike(f"%{q}%")) |
            (models.Customer.city.ilike(f"%{q}%"))
        )
    return query.order_by(models.Customer.name).all()


def get_customer_stats(db: Session, base_query=None) -> dict:
    """Aggregate relevamiento counts over the *whole* filtered set.

    This used to receive the already-paginated list, so the totals described at
    most one page of rows and changed as the user paged.
    """
    from sqlalchemy import func, case

    query = base_query if base_query is not None else db.query(models.Customer)
    query = query.filter(models.Customer.is_active.is_(True))
    rows = query.with_entities(
        func.count(models.Customer.id),
        func.sum(case((models.Customer.relevamiento_status == RelevamientoStatus.EN_PROCESO.value, 1), else_=0)),
        func.sum(case((models.Customer.relevamiento_status == RelevamientoStatus.COMPLETADO.value, 1), else_=0)),
        func.sum(case((models.Customer.relevamiento_status == RelevamientoStatus.PENDIENTE.value, 1), else_=0)),
    ).one()
    return {
        "total": int(rows[0] or 0),
        "en_relevamiento": int(rows[1] or 0),
        "completados": int(rows[2] or 0),
        "pendientes": int(rows[3] or 0),
    }


def get_distinct_customer_names(db: Session):
    return [r.name for r in db.query(models.Customer.name)
            .filter(models.Customer.is_active.is_(True))
            .distinct().order_by(models.Customer.name).all() if r.name]


def get_distinct_plant_names(db: Session):
    return [r.plant for r in db.query(models.Customer.plant)
            .filter(models.Customer.is_active.is_(True))
            .distinct().order_by(models.Customer.plant).all() if r.plant]


def create_customer(db: Session, name: str, plant: str, industry_sector: str,
                    assigned_commercial: str, technical_advisor: str,
                    designer: str, address: str, city: str,
                    status: str = None, relevamiento_status: str = None,
                    member_name: List[str] = None, member_role: List[str] = None,
                    member_phone: List[str] = None,
                    member_reports_to: List[str] = None,
                    member_sector: List[str] = None,
                    observations: str = ""):
    member_name = member_name or []
    member_role = member_role or []
    member_phone = member_phone or []
    member_reports_to = member_reports_to or []
    member_sector = member_sector or []

    team = []
    for i, n in enumerate(member_name):
        if n.strip():
            p = member_phone[i] if i < len(member_phone) else ''
            r = member_role[i] if i < len(member_role) else ''
            rt = member_reports_to[i] if i < len(member_reports_to) else ''
            s = member_sector[i] if i < len(member_sector) else ''
            team.append({"name": n, "role": r, "phone": p, "reports_to": rt, "sector": s})

    form_data = {
        "name": name, "plant": plant, "industry_sector": industry_sector,
        "assigned_commercial": assigned_commercial, "technical_advisor": technical_advisor,
        "designer": designer, "address": address, "city": city, "observations": observations
    }
    calculated_status = calculate_relevo_status(form_data, team)

    new_customer = models.Customer(
        name=name, plant=plant, industry_sector=industry_sector,
        assigned_commercial=assigned_commercial, technical_advisor=technical_advisor,
        designer=designer, address=address, city=city,
        status=status or CustomerStatus.PROSPECTO.value,
        relevamiento_status=relevamiento_status or calculated_status,
        client_team=team, observations=observations
    )
    db.add(new_customer)
    db.flush()

    existing_at = db.query(models.ATAssignment).filter(
        models.ATAssignment.customer_name == name,
        models.ATAssignment.valid_to.is_(None)
    ).first()
    if not existing_at:
        at_assignment = models.ATAssignment(
            customer_name=name,
            technical_advisor=technical_advisor,
            standard_visits=0,
            premium_visits=0,
            status="Activo",
            valid_from=datetime.datetime.utcnow(),
        )
        db.add(at_assignment)

    db.commit()
    return new_customer


def get_customer(db: Session, customer_id: int):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return customer


def update_customer(db: Session, customer_id: int, name: str, plant: str,
                    industry_sector: str, assigned_commercial: str,
                    technical_advisor: str, designer: str, address: str,
                    city: str, status: str, relevamiento_status: Optional[str],
                    member_name: List[str], member_role: List[str],
                    member_phone: List[str],
                    member_reports_to: List[str],
                    member_sector: List[str],
                    observations: str):
    customer = get_customer(db, customer_id)
    old_name = customer.name

    member_name = member_name or []
    member_role = member_role or []
    member_phone = member_phone or []
    member_reports_to = member_reports_to or []
    member_sector = member_sector or []

    team = []
    for i, n in enumerate(member_name):
        if n.strip():
            p = member_phone[i] if i < len(member_phone) else ''
            r = member_role[i] if i < len(member_role) else ''
            rt = member_reports_to[i] if i < len(member_reports_to) else ''
            s = member_sector[i] if i < len(member_sector) else ''
            team.append({"name": n, "role": r, "phone": p, "reports_to": rt, "sector": s})

    form_data = {
        "name": name, "plant": plant, "industry_sector": industry_sector,
        "assigned_commercial": assigned_commercial, "technical_advisor": technical_advisor,
        "designer": designer, "address": address, "city": city, "observations": observations
    }
    calculated_status = calculate_relevo_status(form_data, team)

    customer.name = name
    customer.plant = plant
    customer.industry_sector = industry_sector
    customer.assigned_commercial = assigned_commercial
    customer.technical_advisor = technical_advisor
    customer.designer = designer
    customer.address = address
    customer.city = city
    customer.status = status
    customer.relevamiento_status = calculated_status
    customer.client_team = team
    customer.observations = observations

    db.query(models.ATAssignment).filter(models.ATAssignment.customer_name == old_name).update({
        "customer_name": name,
        "technical_advisor": technical_advisor
    })

    db.commit()
    return customer


def get_customer_plants(db: Session, customer_name: str):
    customers = db.query(models.Customer).filter(models.Customer.name == customer_name).all()
    return [{"id": c.id, "name": c.plant} for c in customers if c.plant]


def get_plant_lines(db: Session, customer_name: str, plant_name: str):
    machines = db.query(models.Machine).join(models.Customer).filter(
        models.Customer.name == customer_name,
        models.Customer.plant == plant_name
    ).all()
    lines = sorted(list(set([m.line for m in machines if m.line])))
    return [{"name": l} for l in lines]


def get_plant_machines(db: Session, customer_name: str, plant_name: str):
    machines = db.query(models.Machine).join(models.Customer).filter(
        models.Customer.name == customer_name,
        models.Customer.plant == plant_name
    ).all()
    return [{"id": m.id, "name": f"{m.brand} {m.model}", "serial": m.serial_number, "line": m.line or "", "status": m.relevamiento_status} for m in machines]


def get_line_machines(db: Session, customer_name: str, plant_name: str, line_name: str):
    machines = db.query(models.Machine).join(models.Customer).filter(
        models.Customer.name == customer_name,
        models.Customer.plant == plant_name,
        models.Machine.line == line_name
    ).all()
    return [{"id": m.id, "name": f"{m.brand} {m.model}", "serial": m.serial_number, "status": m.relevamiento_status} for m in machines]
