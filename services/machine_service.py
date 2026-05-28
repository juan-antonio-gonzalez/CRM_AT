from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional
from sqlalchemy import func
import models
from enums import RelevamientoStatus


def list_machines(db: Session, cliente: str = None, asistente: str = None, q: str = None):
    query = db.query(models.Machine)
    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    assigned_advisors = db.query(models.Customer.technical_advisor).filter(models.Customer.technical_advisor != None).distinct().all()
    assigned_advisor_names = sorted([a[0] for a in assigned_advisors if a[0]])

    customers_for_dropdown = customers_raw
    advisors_for_dropdown = assigned_advisor_names

    cliente_id = None
    if cliente and cliente.strip() != "":
        try:
            cliente_id = int(cliente)
            query = query.filter(models.Machine.customer_id == cliente_id)
            selected_cust = next((c for c in customers_raw if c.id == cliente_id), None)
            if selected_cust and selected_cust.technical_advisor:
                advisors_for_dropdown = [selected_cust.technical_advisor]
        except ValueError:
            pass

    if asistente and asistente.strip() != "":
        query = query.join(models.Customer).filter(models.Customer.technical_advisor == asistente)
        customers_for_dropdown = [c for c in customers_raw if c.technical_advisor == asistente]

    if q and q.strip() != "":
        query = query.filter(
            (models.Machine.serial_number.ilike(f"%{q}%")) |
            (models.Machine.model.ilike(f"%{q}%")) |
            (models.Machine.brand.ilike(f"%{q}%")) |
            (models.Machine.line.ilike(f"%{q}%"))
        )
    machines = query.order_by(models.Machine.brand, models.Machine.model).all()

    total_machines = db.query(func.count(models.Machine.id)).scalar()
    completados = db.query(func.count(models.Machine.id)).filter(models.Machine.relevamiento_status == RelevamientoStatus.COMPLETADO.value).scalar() or 0
    en_proceso = db.query(func.count(models.Machine.id)).filter(models.Machine.relevamiento_status == RelevamientoStatus.EN_PROCESO.value).scalar() or 0
    pendientes = db.query(func.count(models.Machine.id)).filter(models.Machine.relevamiento_status == RelevamientoStatus.PENDIENTE.value).scalar() or 0

    stats = {
        "total": total_machines,
        "completados": completados,
        "en_proceso": en_proceso,
        "pendientes": pendientes,
    }

    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))
    machine_types = db.query(models.MachineType).order_by(models.MachineType.name).all()

    selected_customer = None
    if cliente_id:
        selected_customer = db.query(models.Customer).filter(models.Customer.id == cliente_id).first()

    return {
        "machines": machines,
        "customers": customers_for_dropdown,
        "unique_customer_names": unique_customer_names,
        "machine_types": machine_types,
        "advisors": advisors_for_dropdown,
        "stats": stats,
        "selected_customer_id": cliente_id,
        "selected_asistente": asistente,
        "selected_customer": selected_customer,
        "q": q,
    }


def create_machine(db: Session, serial_number: str, model: str, brand: str,
                   plant_assigned: str, machine_type: str, line: str, customer_id: int):
    existing_machine = db.query(models.Machine).filter(models.Machine.serial_number == serial_number).first()
    if existing_machine:
        return None

    new_machine = models.Machine(
        serial_number=serial_number, model=model, brand=brand,
        plant_assigned=plant_assigned, machine_type=machine_type,
        line=line.upper(), customer_id=customer_id
    )
    db.add(new_machine)
    db.commit()
    return new_machine


def get_machine(db: Session, machine_id: int):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")
    return machine


def update_machine(db: Session, machine_id: int, customer_id: int, serial_number: str,
                   brand: str, model: str, plant_assigned: str, machine_type: str,
                   line: str, status: str):
    machine = get_machine(db, machine_id)
    machine.customer_id = customer_id
    machine.serial_number = serial_number
    machine.brand = brand
    machine.model = model
    machine.plant_assigned = plant_assigned
    machine.machine_type = machine_type
    machine.line = line.upper()
    machine.status = status
    db.commit()
    return machine


def delete_machine(db: Session, machine_id: int, user_id: int = None, username: str = None):
    machine = get_machine(db, machine_id)
    from services.trash_service import move_to_trash
    move_to_trash(db, "machine", machine_id, {
        "serial_number": machine.serial_number, "model": machine.model,
        "brand": machine.brand, "plant_assigned": machine.plant_assigned,
        "machine_type": machine.machine_type, "line": machine.line,
        "status": machine.status,
    }, user_id, username, f"{machine.brand} {machine.model}")
    surveys = db.query(models.TechnicalSurvey).filter(models.TechnicalSurvey.machine_id == machine_id).all()
    for s in surveys:
        s.machine_name_backup = f"{machine.brand} {machine.model}"
        s.machine_serial_backup = machine.serial_number
        s.machine_id = None
    db.delete(machine)
    db.commit()
