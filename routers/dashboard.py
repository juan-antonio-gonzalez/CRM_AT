from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import models
from database import get_db
from services import dashboard_service
import datetime
from templating import templates
from services.utils import month_date_range

router = APIRouter(tags=["dashboard"])


@router.get("/kpi-calidad", response_class=HTMLResponse)
async def kpi_calidad(
    request: Request,
    db: Session = Depends(get_db),
    at: str = Query("", alias="at"),
    cliente: str = Query("", alias="cliente"),
    anio: str = Query("", alias="anio"),
    mes: str = Query("", alias="mes"),
    tema: str = Query("", alias="tema"),
    tipo_producto: str = Query("", alias="tipo_producto"),
    planta: str = Query("", alias="planta"),
):
    today = datetime.datetime.now(datetime.UTC)

    fecha_desde = ""
    fecha_desde, fecha_hasta = month_date_range(anio, mes)

    visitas = dashboard_service.get_visitas_stats(
        db, today, at=at, cliente=cliente,
        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
        tema=tema, impacto="",
        tipo_producto=tipo_producto, planta=planta,
    )

    clientes = (
        db.query(models.Customer.id, models.Customer.name)
        .order_by(models.Customer.name)
        .all()
    )
    advisors = (
        db.query(models.TechnicalAdvisor.name)
        .order_by(models.TechnicalAdvisor.name)
        .all()
    )
    years = sorted(
        db.query(models.TechnicalVisit2.fecha)
        .filter(models.TechnicalVisit2.fecha != "")
        .distinct()
        .all()
    )
    available_years = sorted(set(f[:4] for (f,) in years if f and len(f) >= 4))
    months = [
        ("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"),
        ("04", "Abril"), ("05", "Mayo"), ("06", "Junio"),
        ("07", "Julio"), ("08", "Agosto"), ("09", "Septiembre"),
        ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre"),
    ]

    resp = templates.TemplateResponse(request, 'kpi_calidad.html', {
        "request": request,
        "active_page": "kpi_calidad",
        "today": today,
        "visitas": visitas,
        "filters": {
            "at": at,
            "cliente": cliente,
            "anio": anio,
            "mes": mes,
            "tema": tema,
            "tipo_producto": tipo_producto,
            "planta": planta,
        },
        "advisors": [a[0] for a in advisors],
        "customer_list": clientes,
        "available_years": available_years,
        "months": months,
    })
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    at: str = Query("", alias="at"),
    cliente: str = Query("", alias="cliente"),
    anio: str = Query("", alias="anio"),
    mes: str = Query("", alias="mes"),
    db: Session = Depends(get_db)
):
    today = datetime.datetime.now(datetime.UTC)

    fecha_desde = ""
    fecha_desde, fecha_hasta = month_date_range(anio, mes)

    clientes = dashboard_service.get_clientes_stats(db, at=at)
    visitas = dashboard_service.get_visitas_stats(db, today, at=at, cliente=cliente, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    maquinas = dashboard_service.get_maquinas_stats(db, at=at, cliente=cliente)
    minutas = dashboard_service.get_minutas_stats(db, at=at, cliente=cliente)

    advisors = (
        db.query(models.TechnicalAdvisor.name)
        .order_by(models.TechnicalAdvisor.name)
        .all()
    )
    customer_list = (
        db.query(models.Customer.id, models.Customer.name)
        .order_by(models.Customer.name)
        .all()
    )
    years = sorted(
        db.query(models.TechnicalVisit2.fecha)
        .filter(models.TechnicalVisit2.fecha != "")
        .distinct()
        .all()
    )
    available_years = sorted(set(f[:4] for (f,) in years if f and len(f) >= 4))

    months = [
        ("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"),
        ("04", "Abril"), ("05", "Mayo"), ("06", "Junio"),
        ("07", "Julio"), ("08", "Agosto"), ("09", "Septiembre"),
        ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre"),
    ]

    return templates.TemplateResponse(request, 'dashboard.html', {
        "request": request,
        "active_page": "dashboard",
        "today": today,
        "clientes": clientes,
        "visitas": visitas,
        "maquinas": maquinas,
        "minutas": minutas,
        "advisors": [a[0] for a in advisors],
        "customer_list": customer_list,
        "available_years": available_years,
        "months": months,
        "filters": {"at": at, "cliente": cliente, "anio": anio, "mes": mes},
    })


@router.get("/search", response_class=HTMLResponse)
async def global_search(request: Request, q: str = Query(...), db: Session = Depends(get_db)):
    customers = db.query(models.Customer).filter(
        (models.Customer.name.ilike(f"%{q}%")) |
        (models.Customer.plant.ilike(f"%{q}%"))
    ).limit(5).all()

    products = db.query(models.Product).filter(
        (models.Product.name.ilike(f"%{q}%")) |
        (models.Product.et_number.ilike(f"%{q}%"))
    ).limit(5).all()

    machines = db.query(models.Machine).filter(
        (models.Machine.serial_number.ilike(f"%{q}%")) |
        (models.Machine.model.ilike(f"%{q}%"))
    ).limit(5).all()

    return templates.TemplateResponse(request, 'layout.html', {
        "request": request,
        "search_results": {
            "customers": customers,
            "products": products,
            "machines": machines
        },
        "search_query": q,
        "active_page": "dashboard"
    })
