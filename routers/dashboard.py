from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import models
from database import get_db
from services import dashboard_service
import datetime
from templating import templates
from routers import publico
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
    # Sin sesión, la raíz muestra la presentación en lugar de mandar al login.
    #
    # Es lo primero que ve alguien que llega al dominio, y también el robot de un
    # filtro web: hasta ahora rebotaba al formulario de acceso, así que lo único
    # que se podía leer del sitio era un login. Ver `routers/publico.py`.
    if not getattr(request.state, "user", None):
        return templates.TemplateResponse(request, 'bienvenida.html', {
            "request": request,
            "descripcion": publico.DESCRIPCION,
        })

    today = datetime.datetime.now(datetime.UTC)

    fecha_desde = ""
    fecha_desde, fecha_hasta = month_date_range(anio, mes)

    clientes = dashboard_service.get_clientes_stats(db, at=at)
    visitas = dashboard_service.get_visitas_stats(db, today, at=at, cliente=cliente, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    maquinas = dashboard_service.get_maquinas_stats(db, at=at, cliente=cliente)
    minutas = dashboard_service.get_minutas_stats(db, at=at, cliente=cliente)
    atencion = dashboard_service.get_atencion(db, today)
    comparacion = dashboard_service.get_comparacion(
        db, today, anio=anio, mes=mes, at=at, cliente=cliente)

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
        "atencion": atencion,
        "comparacion": comparacion,
        "advisors": [a[0] for a in advisors],
        "customer_list": customer_list,
        "available_years": available_years,
        "months": months,
        "filters": {"at": at, "cliente": cliente, "anio": anio, "mes": mes},
    })
