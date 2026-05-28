from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
import models
from database import get_db
from services import customer_service, pagination as pg

router = APIRouter(tags=["customers"])
templates = Jinja2Templates(directory="templates")


@router.get("/clientes", response_class=HTMLResponse)
async def list_customers(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.Customer)
    if q:
        query = query.filter(
            (models.Customer.name.ilike(f"%{q}%")) |
            (models.Customer.plant.ilike(f"%{q}%")) |
            (models.Customer.industry_sector.ilike(f"%{q}%")) |
            (models.Customer.city.ilike(f"%{q}%"))
        )
    total = query.count()
    page, per_page, offset = pg.paginate(page, per_page)
    customers = query.order_by(models.Customer.name).offset(offset).limit(per_page).all()
    stats = customer_service.get_customer_stats(customers)
    client_names = db.query(models.ClientName).order_by(models.ClientName.name).all()
    plant_names = db.query(models.PlantName).order_by(models.PlantName.name).all()

    return templates.TemplateResponse("clientes.html", {
        "request": request, "customers": customers, "stats": stats, "q": q, "active_page": "clientes",
        "advisors": db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all(),
        "designers": db.query(models.Designer).order_by(models.Designer.name).all(),
        "commercials": db.query(models.CommercialAdvisor).order_by(models.CommercialAdvisor.name).all(),
        "sectors": db.query(models.IndustrialSector).order_by(models.IndustrialSector.name).all(),
        "client_names": client_names,
        "plant_names": plant_names,
        "pagination": pg.build_pagination(page, per_page, total),
    })


@router.get("/nuevo-cliente", response_class=HTMLResponse)
async def new_customer_form(request: Request, db: Session = Depends(get_db)):
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    designers = db.query(models.Designer).order_by(models.Designer.name).all()
    commercials = db.query(models.CommercialAdvisor).order_by(models.CommercialAdvisor.name).all()
    sectors = db.query(models.IndustrialSector).order_by(models.IndustrialSector.name).all()
    client_names = db.query(models.ClientName).order_by(models.ClientName.name).all()
    plant_names = db.query(models.PlantName).order_by(models.PlantName.name).all()
    return templates.TemplateResponse("nuevo_cliente.html", {
        "request": request,
        "advisors": advisors,
        "designers": designers,
        "commercials": commercials,
        "sectors": sectors,
        "client_names": client_names,
        "plant_names": plant_names,
        "active_page": "clientes"
    })


@router.get("/api/cliente-plantas/{customer_name}")
async def get_customer_plants(customer_name: str, db: Session = Depends(get_db)):
    return customer_service.get_customer_plants(db, customer_name)


@router.get("/api/plantas-lineas/{customer_name}/{plant_name}")
async def get_plant_lines(customer_name: str, plant_name: str, db: Session = Depends(get_db)):
    return customer_service.get_plant_lines(db, customer_name, plant_name)


@router.get("/api/linea-maquinas/{customer_name}/{plant_name}/{line_name}")
async def get_line_machines(customer_name: str, plant_name: str, line_name: str, db: Session = Depends(get_db)):
    return customer_service.get_line_machines(db, customer_name, plant_name, line_name)


@router.get("/api/planta-maquinas/{customer_name}/{plant_name}")
async def get_plant_machines(customer_name: str, plant_name: str, db: Session = Depends(get_db)):
    return customer_service.get_plant_machines(db, customer_name, plant_name)


@router.post("/nuevo-cliente")
async def create_customer(
    name: str = Form(...), plant: str = Form(...), industry_sector: str = Form(...),
    assigned_commercial: str = Form(...), technical_advisor: str = Form(...),
    designer: str = Form(...), address: str = Form(...), city: str = Form(...),
    status: str = Form("Prospecto"), relevamiento_status: Optional[str] = Form(None),
    member_name: List[str] = Form([]), member_role: List[str] = Form([]),
    member_email: List[str] = Form([]), member_phone: List[str] = Form([]),
    observations: str = Form(""),
    db: Session = Depends(get_db)
):
    customer_service.create_customer(db, name, plant, industry_sector, assigned_commercial,
                                      technical_advisor, designer, address, city,
                                      status, relevamiento_status,
                                      member_name, member_role, member_email, member_phone, observations)
    return RedirectResponse(url="/clientes", status_code=303)


@router.get("/editar-cliente/{customer_id}", response_class=HTMLResponse)
async def edit_customer_form(customer_id: int, request: Request, db: Session = Depends(get_db)):
    # If not an AJAX request, redirect to the clientes page (the edit modal opens from there)
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return RedirectResponse(url="/clientes", status_code=302)
    customer = customer_service.get_customer(db, customer_id)
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    designers = db.query(models.Designer).order_by(models.Designer.name).all()
    commercials = db.query(models.CommercialAdvisor).order_by(models.CommercialAdvisor.name).all()
    sectors = db.query(models.IndustrialSector).order_by(models.IndustrialSector.name).all()
    client_names = db.query(models.ClientName).order_by(models.ClientName.name).all()
    plant_names = db.query(models.PlantName).order_by(models.PlantName.name).all()
    return templates.TemplateResponse("_editar_cliente_partial.html", {
        "request": request,
        "customer": customer,
        "advisors": advisors,
        "designers": designers,
        "commercials": commercials,
        "sectors": sectors,
        "client_names": client_names,
        "plant_names": plant_names,
    })


@router.post("/editar-cliente/{customer_id}")
async def update_customer(
    customer_id: int,
    name: str = Form(...), plant: str = Form(...), industry_sector: str = Form(...),
    assigned_commercial: str = Form(...), technical_advisor: str = Form(...),
    designer: str = Form(...), address: str = Form(...), city: str = Form(...),
    status: str = Form(...), relevamiento_status: Optional[str] = Form(None),
    member_name: List[str] = Form([]), member_role: List[str] = Form([]),
    member_email: List[str] = Form([]), member_phone: List[str] = Form([]),
    observations: str = Form(""),
    db: Session = Depends(get_db)
):
    customer_service.update_customer(db, customer_id, name, plant, industry_sector,
                                      assigned_commercial, technical_advisor, designer,
                                      address, city, status, relevamiento_status,
                                      member_name, member_role, member_email, member_phone, observations)
    return RedirectResponse(url="/clientes", status_code=303)


@router.get("/cliente-reporte/{customer_id}", response_class=HTMLResponse)
async def customer_report(customer_id: int, request: Request, db: Session = Depends(get_db)):
    customer = customer_service.get_customer(db, customer_id)
    machines = db.query(models.Machine).filter(models.Machine.customer_id == customer_id).order_by(models.Machine.brand, models.Machine.model).all()
    visits = db.query(models.TechnicalVisit).filter(models.TechnicalVisit.customer_id == customer_id).order_by(models.TechnicalVisit.date.desc()).all()
    return templates.TemplateResponse("cliente_reporte.html", {
        "request": request,
        "customer": customer,
        "machines": machines,
        "visits": visits,
        "generation_date": __import__('datetime').datetime.now(),
        "active_page": "clientes"
    })


@router.post("/eliminar-cliente/{customer_id}")
async def delete_customer(customer_id: int, request: Request, redirect: str = Query("/clientes"), db: Session = Depends(get_db)):
    user = getattr(request.state, 'user', None)
    uid = int(user["sub"]) if user else None
    uname = user.get("username") if user else None
    customer_service.delete_customer(db, customer_id, uid, uname)
    return RedirectResponse(url=redirect, status_code=303)
