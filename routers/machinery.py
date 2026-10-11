from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
import models
from database import get_db
from services import machine_service, pagination as pg
from templating import templates

router = APIRouter(tags=["machinery"])


def _machine_filters(db: Session, cliente=None, asistente=None, q=None):
    """Consulta de máquinas con los filtros del listado.

    La usan el listado y la exportación, para que exportar respete exactamente los
    mismos filtros que se están viendo en pantalla.
    """
    query = db.query(models.Machine).options(joinedload(models.Machine.customer))

    if cliente and str(cliente).strip() != "":
        try:
            query = query.filter(models.Machine.customer_id == int(cliente))
        except (TypeError, ValueError):
            pass

    if asistente and str(asistente).strip() != "":
        query = query.join(models.Customer).filter(
            models.Customer.technical_advisor == asistente)

    if q and str(q).strip() != "":
        patron = f"%{q}%"
        query = query.filter(
            (models.Machine.serial_number.ilike(patron)) |
            (models.Machine.model.ilike(patron)) |
            (models.Machine.brand.ilike(patron)) |
            (models.Machine.line.ilike(patron))
        )

    return query


@router.get("/maquinaria/exportar-excel")
async def exportar_maquinaria_excel(
    cliente: Optional[str] = Query(None),
    asistente: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Exporta el listado filtrado de máquinas a Excel."""
    from services.excel import hoja_excel, nombre_con_fecha

    maquinas = (
        _machine_filters(db, cliente=cliente, asistente=asistente, q=q)
        .order_by(models.Machine.brand, models.Machine.model)
        .all()
    )

    filas = []
    for m in maquinas:
        filas.append([
            m.customer.name if m.customer else "",
            m.plant_assigned,
            m.brand,
            m.model,
            m.machine_type,
            m.serial_number,
            m.line,
            m.status,
            m.relevamiento_status,
            "Sí" if m.is_active else "No",
        ])

    return hoja_excel(
        "Máquinas",
        ["Cliente", "Planta", "Marca", "Modelo", "Tipo", "Nº de serie", "Línea",
         "Estado", "Relevamiento", "Activa"],
        filas,
        nombre_con_fecha("maquinas"),
    )


@router.get("/maquinaria", response_class=HTMLResponse)
async def list_machinery(
    request: Request,
    cliente: Optional[str] = Query(None),
    asistente: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    # joinedload: la plantilla lee machine.customer en cada fila (evita N+1).
    query = _machine_filters(db, cliente=cliente, asistente=asistente, q=q)

    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    assigned_advisors = db.query(models.Customer.technical_advisor).filter(
        models.Customer.technical_advisor != None
    ).distinct().all()
    assigned_advisor_names = sorted([a[0] for a in assigned_advisors if a[0]])

    customers_for_dropdown = customers_raw
    advisors_for_dropdown = assigned_advisor_names
    cliente_id = None

    if cliente and cliente.strip() != "":
        try:
            cliente_id = int(cliente)
            selected_cust = next((c for c in customers_raw if c.id == cliente_id), None)
            if selected_cust and selected_cust.technical_advisor:
                advisors_for_dropdown = [selected_cust.technical_advisor]
        except ValueError:
            pass

    if asistente and asistente.strip() != "":
        customers_for_dropdown = [c for c in customers_raw if c.technical_advisor == asistente]

    total = query.count()
    page, per_page, offset = pg.paginate(page, per_page)
    machines = query.order_by(models.Machine.brand, models.Machine.model).offset(offset).limit(per_page).all()

    total_machines = db.query(func.count(models.Machine.id)).scalar()
    from enums import RelevamientoStatus
    completados = db.query(func.count(models.Machine.id)).filter(
        models.Machine.relevamiento_status == RelevamientoStatus.COMPLETADO.value
    ).scalar() or 0
    en_proceso = db.query(func.count(models.Machine.id)).filter(
        models.Machine.relevamiento_status == RelevamientoStatus.EN_PROCESO.value
    ).scalar() or 0
    pendientes = db.query(func.count(models.Machine.id)).filter(
        models.Machine.relevamiento_status == RelevamientoStatus.PENDIENTE.value
    ).scalar() or 0

    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))
    machine_types = db.query(models.MachineType).order_by(models.MachineType.name).all()
    selected_customer = None
    if cliente_id:
        selected_customer = db.query(models.Customer).filter(models.Customer.id == cliente_id).first()

    return templates.TemplateResponse(request, 'maquinaria.html', {
        "request": request,
        "machines": machines,
        "customers": customers_for_dropdown,
        "unique_customer_names": unique_customer_names,
        "machine_types": machine_types,
        "advisors": advisors_for_dropdown,
        "stats": {"total": total_machines, "completados": completados, "en_proceso": en_proceso, "pendientes": pendientes},
        "selected_customer_id": cliente_id,
        "selected_asistente": asistente,
        "selected_customer": selected_customer,
        "q": q,
        "pagination": pg.build_pagination(page, per_page, total),
        "active_page": "maquinaria"
    })


@router.post("/nuevo-maquinaria")
async def create_machine(
    serial_number: str = Form(...), machine_model: str = Form(..., alias="model_name"), brand: str = Form(...),
    plant_assigned: str = Form(...), machine_type: str = Form(...), line: str = Form(""),
    customer_id: int = Form(...),
    db: Session = Depends(get_db)
):
    result = machine_service.create_machine(db, serial_number, machine_model, brand,
                                             plant_assigned, machine_type, line, customer_id)
    if result is None:
        return RedirectResponse(url="/maquinaria?error=duplicate_serial", status_code=303)
    return RedirectResponse(url="/maquinaria?success=machine_created", status_code=303)


@router.get("/editar-maquinaria/{machine_id}", response_class=HTMLResponse)
async def edit_machine_form(machine_id: int, request: Request, db: Session = Depends(get_db)):
    machine = machine_service.get_machine(db, machine_id)
    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))
    machine_types = db.query(models.MachineType).order_by(models.MachineType.name).all()

    current_customer = db.query(models.Customer).filter(models.Customer.id == machine.customer_id).first()
    current_plants = []
    if current_customer:
        customers_with_same_name = db.query(models.Customer).filter(models.Customer.name == current_customer.name).all()
        current_plants = [{"id": c.id, "name": c.plant} for c in customers_with_same_name if c.plant]

    return templates.TemplateResponse(request, 'editar_maquinaria.html', {
        "request": request,
        "machine": machine,
        "unique_customer_names": unique_customer_names,
        "current_plants": current_plants,
        "machine_types": machine_types,
        "active_page": "maquinaria"
    })


@router.get("/editar-maquinaria/{machine_id}/partial", response_class=HTMLResponse)
async def edit_machine_partial(machine_id: int, request: Request, db: Session = Depends(get_db)):
    machine = machine_service.get_machine(db, machine_id)
    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    unique_customer_names = sorted(list(set([c.name for c in customers_raw])))
    machine_types = db.query(models.MachineType).order_by(models.MachineType.name).all()

    current_customer = db.query(models.Customer).filter(models.Customer.id == machine.customer_id).first()
    current_plants = []
    if current_customer:
        customers_with_same_name = db.query(models.Customer).filter(models.Customer.name == current_customer.name).all()
        current_plants = [{"id": c.id, "name": c.plant} for c in customers_with_same_name if c.plant]

    return templates.TemplateResponse(request, '_editar_maquinaria_partial.html', {
        "request": request,
        "machine": machine,
        "unique_customer_names": unique_customer_names,
        "current_plants": current_plants,
        "machine_types": machine_types,
    })


@router.post("/editar-maquinaria/{machine_id}")
async def update_machine(
    machine_id: int,
    customer_id: int = Form(...),
    serial_number: str = Form(...),
    brand: str = Form(...),
    machine_model: str = Form(..., alias="model_name"),
    plant_assigned: str = Form(...),
    machine_type: str = Form(...),
    line: str = Form(""),
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    machine_service.update_machine(db, machine_id, customer_id, serial_number, brand,
                                    machine_model, plant_assigned, machine_type, line, status)
    return RedirectResponse(url="/maquinaria", status_code=303)


@router.post("/eliminar-maquinaria/{machine_id}")
async def delete_machine(machine_id: int, request: Request, redirect: str = Query("/maquinaria"), db: Session = Depends(get_db)):
    user = getattr(request.state, 'user', None)
    uid = int(user["sub"]) if user else None
    uname = user.get("username") if user else None
    machine_service.delete_machine(db, machine_id, uid, uname)
    return RedirectResponse(url=redirect, status_code=303)
