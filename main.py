from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine
from enums import RelevamientoStatus, ProductStatus, CustomerStatus
import datetime
import json
import secrets
import urllib.parse

from config import settings
from logger import setup_logging, get_logger
from security import get_current_user, generate_csrf_token, verify_csrf_token, COOKIE_NAME

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        nonce = secrets.token_hex(16)
        request.state.script_nonce = nonce
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "font-src 'self' fonts.gstatic.com; "
            f"script-src 'self' 'nonce-{nonce}' cdn.jsdelivr.net cdn.tailwindcss.com unpkg.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

CSRF_EXEMPT_PATHS = {"/auth/login", "/auth/register"}
PUBLIC_PATHS = {"/auth/login", "/auth/logout"}


@app.middleware("http")
async def auth_csrf_middleware(request: Request, call_next):
    user = get_current_user(request)
    csrf = None
    if user:
        csrf = generate_csrf_token(int(user["sub"]))
    request.state.user = user
    request.state.csrf_token = csrf

    path = request.url.path.rstrip("/")

    if not user and path not in PUBLIC_PATHS and not path.startswith("/static/"):
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"message": "No autenticado"})
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=303)

    if request.method in ("POST", "PUT", "DELETE") and user:
        if path not in CSRF_EXEMPT_PATHS and not path.startswith("/auth/logout"):
            content_type = request.headers.get("content-type", "")
            if "form-urlencoded" in content_type or "form-data" in content_type:
                try:
                    body = await request.body()
                    params = urllib.parse.parse_qs(body.decode())
                    token = params.get("csrf_token", [""])[0]
                    uid = int(user["sub"])
                    if not token or not verify_csrf_token(token, uid):
                        logger.warning("CSRF validation failed for %s from user %s", path, user.get("username"))
                        if path.startswith("/api/"):
                            return JSONResponse(status_code=403, content={"message": "CSRF token inválido"})
                        from fastapi.responses import RedirectResponse
                        return RedirectResponse(url="/auth/login", status_code=303)
                except Exception as e:
                    logger.warning("CSRF check error on %s: %s", path, e)

    return await call_next(request)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"},
    )


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters["from_json"] = lambda s: json.loads(s) if isinstance(s, str) else s


def inject_auth(request: Request, extra: dict = None) -> dict:
    ctx = {"request": request}
    if hasattr(request.state, "user"):
        ctx["current_user"] = request.state.user
    if hasattr(request.state, "csrf_token"):
        ctx["csrf_token"] = request.state.csrf_token
    if hasattr(request.state, "script_nonce"):
        ctx["script_nonce"] = request.state.script_nonce
    if extra:
        ctx.update(extra)
    return ctx


def init_db():
    db = SessionLocal()
    try:
        if db.query(models.Product).count() == 0:
            db.add_all([
                models.Product(name="Caja Estándar A1", et_number="ET-001", material="Corrugado Simple", manufacturing_route="Troquelado > Pegado", dimensions_l=400, dimensions_a=300, dimensions_h=200, status=ProductStatus.ACTIVO.value, last_modified="Hace 2 días"),
                models.Product(name="Contenedor Reforzado", et_number="ET-002", material="Corrugado Doble", manufacturing_route="Corte > Ranurado", dimensions_l=800, dimensions_a=600, dimensions_h=500, status=ProductStatus.ACTIVO.value, last_modified="Hace 5 días"),
            ])
            db.flush()

        if db.query(models.Customer).count() == 0:
            c1 = models.Customer(name="Steel Metrics S.A.", plant="Planta Monterrey", industry_sector="Metalurgia", assigned_commercial="Carlos Pérez", city="Monterrey", status=CustomerStatus.CLIENTE.value)
            c2 = models.Customer(name="AutoVanguard Corp.", plant="Sede Querétaro", industry_sector="Automotriz", assigned_commercial="Elena Rodríguez", city="Querétaro", status=CustomerStatus.CLIENTE.value)
            c3 = models.Customer(name="Envases del Norte S.A.", plant="Planta Saltillo", industry_sector="Alimentos y Bebidas", assigned_commercial="Miguel Ángel", city="Saltillo", status=CustomerStatus.PROSPECTO.value)
            db.add_all([c1, c2, c3])
            db.flush()

            db.add_all([
                models.Machine(serial_number="SN-99821-X", model="GA 37VSD", brand="Atlas Copco", plant_assigned="Planta Monterrey - Línea 1", status="Operativo", relevamiento_status=RelevamientoStatus.COMPLETADO.value, customer_id=c1.id),
                models.Machine(serial_number="SN-99822-X", model="ZR 300", brand="Atlas Copco", plant_assigned="Planta Monterrey - Línea 2", status="Operativo", relevamiento_status=RelevamientoStatus.PENDIENTE.value, customer_id=c1.id),
                models.Machine(serial_number="SN-44512-Y", model="1LE1001", brand="Siemens", plant_assigned="Sede Querétaro - Nave A", status="Operativo", relevamiento_status=RelevamientoStatus.EN_PROCESO.value, customer_id=c2.id),
                models.Machine(serial_number="SN-44513-Y", model="ACS580", brand="ABB", plant_assigned="Sede Querétaro - Nave A", status="Mantenimiento", relevamiento_status=RelevamientoStatus.PENDIENTE.value, customer_id=c2.id),
                models.Machine(serial_number="SN-44514-Y", model="G120", brand="Siemens", plant_assigned="Sede Querétaro - Nave B", status="Operativo", relevamiento_status=RelevamientoStatus.PENDIENTE.value, customer_id=c2.id),
                models.Machine(serial_number="SN-77101-Z", model="FlexLine 200", brand="Bosch", plant_assigned="Planta Saltillo", status="Operativo", relevamiento_status=RelevamientoStatus.PENDIENTE.value, customer_id=c3.id),
            ])
            db.flush()

            db.add_all([
                models.TechnicalAdvisor(name="Ing. Roberto Gómez"),
                models.TechnicalAdvisor(name="Ing. Alicia Torres"),
                models.Designer(name="Arq. Studio Alpha"),
                models.Designer(name="Design Pro S.A."),
                models.CommercialAdvisor(name="Carlos Pérez"),
                models.CommercialAdvisor(name="Elena Rodríguez"),
                models.IndustrialSector(name="Alimentos y Bebidas"),
                models.IndustrialSector(name="Automotriz"),
                models.IndustrialSector(name="Farmacéutica"),
                models.IndustrialSector(name="Metalurgia"),
            ])
            db.flush()

        if db.query(models.User).count() == 0:
            from security import hash_password
            admin = models.User(
                username="admin",
                email="admin@crm-at.com",
                hashed_password=hash_password("admin123"),
                full_name="Administrador",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.flush()

        db.commit()
    except Exception as e:
        logger.error("DB Init Error: %s", e)
        db.rollback()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    # Migrations and seed data are handled by run.py before the server starts.
    logger.info("App ready")

from routers import auth as auth_router
from routers import dashboard as dashboard_router
from routers import products as products_router
from routers import customers as customers_router
from routers import machinery as machinery_router
from routers import visits as visits_router
from routers import relevamiento as relevamiento_router
from routers import infraestructura as infra_router
from routers import kpis as kpis_router
from routers import seguimiento as seguimiento_router
from routers import configuracion as config_router
from routers import trash as trash_router

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(products_router.router)
app.include_router(customers_router.router)
app.include_router(machinery_router.router)
app.include_router(visits_router.router)
app.include_router(relevamiento_router.router)
app.include_router(infra_router.router)
app.include_router(kpis_router.router)
app.include_router(seguimiento_router.router)
app.include_router(config_router.router)
app.include_router(trash_router.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
