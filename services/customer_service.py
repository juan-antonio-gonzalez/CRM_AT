from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
import models
from enums import RelevamientoStatus, CustomerStatus
from utils import calculate_relevo_status


def list_customers(db: Session, q: str = None):
    query = db.query(models.Customer)
    if q:
        query = query.filter(
            (models.Customer.name.ilike(f"%{q}%")) |
            (models.Customer.plant.ilike(f"%{q}%")) |
            (models.Customer.industry_sector.ilike(f"%{q}%")) |
            (models.Customer.city.ilike(f"%{q}%"))
        )
    return query.all()


def get_customer_stats(customers: list):
    return {
        "total": len(customers),
        "en_relevamiento": sum(1 for c in customers if c.relevamiento_status == RelevamientoStatus.EN_PROCESO.value),
        "completados": sum(1 for c in customers if c.relevamiento_status == RelevamientoStatus.COMPLETADO.value),
        "pendientes": sum(1 for c in customers if c.relevamiento_status == RelevamientoStatus.PENDIENTE.value)
    }


def get_distinct_customer_names(db: Session):
    return [r.name for r in db.query(models.Customer.name).distinct().order_by(models.Customer.name).all() if r.name]


def get_distinct_plant_names(db: Session):
    return [r.plant for r in db.query(models.Customer.plant).distinct().order_by(models.Customer.plant).all() if r.plant]


def create_customer(db: Session, name: str, plant: str, industry_sector: str,
                    assigned_commercial: str, technical_advisor: str,
                    designer: str, address: str, city: str,
                    status: str = None, relevamiento_status: str = None,
                    member_name: List[str] = None, member_role: List[str] = None,
                    member_email: List[str] = None, member_phone: List[str] = None,
                    observations: str = ""):
    member_name = member_name or []
    member_role = member_role or []
    member_email = member_email or []
    member_phone = member_phone or []

    team = []
    for i, n in enumerate(member_name):
        if n.strip():
            p = member_phone[i] if i < len(member_phone) else ''
            r = member_role[i] if i < len(member_role) else ''
            e = member_email[i] if i < len(member_email) else ''
            team.append({"name": n, "role": r, "email": e, "phone": p})

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
                    member_email: List[str], member_phone: List[str],
                    observations: str):
    customer = get_customer(db, customer_id)
    old_name = customer.name

    member_name = member_name or []
    member_role = member_role or []
    member_email = member_email or []
    member_phone = member_phone or []

    team = []
    for i, n in enumerate(member_name):
        if n.strip():
            p = member_phone[i] if i < len(member_phone) else ''
            r = member_role[i] if i < len(member_role) else ''
            e = member_email[i] if i < len(member_email) else ''
            team.append({"name": n, "role": r, "email": e, "phone": p})

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


def delete_customer(db: Session, customer_id: int, user_id: int = None, username: str = None):
    customer = get_customer(db, customer_id)
    from services.trash_service import move_to_trash
    move_to_trash(db, "customer", customer_id, {
        "name": customer.name, "plant": customer.plant,
        "industry_sector": customer.industry_sector,
        "assigned_commercial": customer.assigned_commercial,
        "technical_advisor": customer.technical_advisor,
        "designer": customer.designer,
        "address": customer.address, "city": customer.city,
        "status": customer.status,
        "observations": customer.observations,
        "client_team": customer.client_team,
    }, user_id, username, customer.name)
    visits = db.query(models.TechnicalVisit).filter(models.TechnicalVisit.customer_id == customer_id).all()
    for v in visits:
        v.customer_name_backup = customer.name
        v.customer_id = None
    machines = db.query(models.Machine).filter(models.Machine.customer_id == customer_id).all()
    for m in machines:
        m.customer_id = None
    infra_surveys = db.query(models.InfrastructureSurvey).filter(models.InfrastructureSurvey.customer_id == customer_id).all()
    for s in infra_surveys:
        s.customer_id = None
    db.delete(customer)
    db.commit()


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
