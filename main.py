from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError

import models
from database import SessionLocal, engine
from enums import RelevamientoStatus, ProductStatus, CustomerStatus
import datetime
import json
import re
import secrets
import urllib.parse

from config import settings
from logger import setup_logging, get_logger
from security import get_current_user, generate_csrf_token, verify_csrf_token, COOKIE_NAME
from templating import templates

setup_logging()
logger = get_logger(__name__)


def _schema_revision() -> str:
    """Return the Alembic revision recorded in the database, if any."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            return row[0] if row else "sin migraciones"
    except Exception as exc:  # pragma: no cover - depends on DB state
        logger.warning("No se pudo leer alembic_version: %s", exc)
        return "desconocida"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup checks.

    NOTE: we deliberately do NOT call ``Base.metadata.create_all()`` here.
    Schema creation is Alembic's job (``alembic upgrade head``). ``create_all``
    only ever issues ``CREATE TABLE IF NOT EXISTS``, so it silently masked every
    missing column and made a broken production schema look healthy locally.
    """
    rev = _schema_revision()
    logger.info("Base de datos: PostgreSQL")
    logger.info("Revision de esquema (alembic): %s", rev)
    if rev in ("sin migraciones", "desconocida"):
        logger.warning(
            "No hay revision de Alembic aplicada. Ejecuta 'alembic upgrade head' "
            "antes de usar la aplicacion."
        )
    logger.info("App lista")
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Paths that must be reachable without a session.
PUBLIC_PATHS = {"/auth/login", "/auth/logout", "/health", "/favicon.ico"}


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
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            f"script-src 'self' 'unsafe-inline' 'nonce-{nonce}'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

CSRF_EXEMPT_PATHS = {"/auth/login", "/auth/register"}


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
        return RedirectResponse(url="/auth/login", status_code=303)

    if request.method in ("POST", "PUT", "DELETE") and user:
        if path not in CSRF_EXEMPT_PATHS and not path.startswith("/auth/logout"):
            content_type = request.headers.get("content-type", "")
            if "form-urlencoded" in content_type or "form-data" in content_type:
                # El token se lee del formulario ya parseado, no con parse_qs sobre
                # el cuerpo crudo. Con `multipart/form-data` —cualquier formulario
                # con archivos— parse_qs fallaba, la excepción se tragaba y la
                # petición **pasaba sin validar**. La comprobación tiene que fallar
                # cerrada: si no se puede leer el token, se rechaza.
                try:
                    # Se lee el cuerpo crudo: `request.form()` consume el stream y
                    # después FastAPI no puede volver a parsearlo (devolvía 422).
                    # `request.body()` deja el cuerpo cacheado, así que el endpoint
                    # lo sigue leyendo sin problema.
                    body = await request.body()
                    token = _token_csrf(body, content_type)
                    uid = int(user["sub"])
                    if not token or not verify_csrf_token(token, uid):
                        logger.warning("CSRF validation failed for %s from user %s",
                                       path, user.get("username"))
                        if path.startswith("/api/"):
                            return JSONResponse(status_code=403,
                                                content={"message": "CSRF token inválido"})
                        return RedirectResponse(url="/auth/login", status_code=303)
                except Exception as e:
                    logger.warning("CSRF check error on %s: %s", path, e)
                    if path.startswith("/api/"):
                        return JSONResponse(status_code=403,
                                            content={"message": "No se pudo validar la petición"})
                    return RedirectResponse(url="/auth/login", status_code=303)

    return await call_next(request)


def _token_csrf(body: bytes, content_type: str) -> str:
    """Extrae `csrf_token` del cuerpo, sea urlencoded o multipart.

    Con `multipart/form-data` —cualquier formulario con archivos— no se puede usar
    `parse_qs`, que era lo que hacía fallar la comprobación y dejaba pasar la
    petición sin validar.
    """
    texto = body.decode("utf-8", errors="replace")
    if "form-urlencoded" in content_type:
        params = urllib.parse.parse_qs(texto)
        return params.get("csrf_token", [""])[0]
    # Multipart: el nombre va en el Content-Disposition y el valor después de la
    # línea en blanco que separa los encabezados de la parte.
    # Después del nombre vienen los encabezados de la parte, una línea en blanco y
    # el valor. El `(?!\r?\n)` evita que el bloque se coma la línea en blanco y
    # siga de largo hasta el último campo del formulario.
    m = re.search(r'name="csrf_token"(?:\r?\n(?![\r\n])[^\r\n]*)*\r?\n\r?\n([^\r\n]+)',
                  texto)
    return m.group(1).strip() if m else ""


def _wants_html(request: Request) -> bool:
    """True when the client is a browser navigating, not an API call."""
    if request.url.path.startswith(("/api/", "/static/")):
        return False
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return False
    return True


def _render_error(request: Request, status_code: int, message: str):
    """Render a styled HTML error page for browser requests."""
    if _wants_html(request):
        try:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "request": request,
                    "status_code": status_code,
                    "message": message,
                    "current_user": getattr(request.state, "user", None),
                    "csrf_token": getattr(request.state, "csrf_token", None),
                    "script_nonce": getattr(request.state, "script_nonce", ""),
                },
                status_code=status_code,
            )
        except Exception as exc:  # pragma: no cover - template must never mask the error
            logger.error("Fallo al renderizar error.html: %s", exc)
    return JSONResponse(status_code=status_code, content={"message": message})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Serve HTML error pages (404/403/...) instead of raw JSON in the browser."""
    detail = exc.detail if isinstance(exc.detail, str) else "Error"
    return _render_error(request, exc.status_code, detail)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Turn constraint violations into a readable message instead of a 500.

    Previously a duplicate ``et_number``, a repeated catalogue name or an orphan
    foreign key produced ``sqlalchemy.exc.IntegrityError`` and the user got a
    bare 500 / raw JSON. We surface which constraint failed.
    """
    from database import SessionLocal
    SessionLocal().rollback()  # release the poisoned connection

    raw = str(getattr(exc, "orig", exc))
    low = raw.lower()

    if "unique" in low or "duplicate key" in low:
        status, message = 409, (
            "Ya existe un registro con ese valor. Revisá los campos únicos "
            "(por ejemplo el número ET, el nombre o el número de serie)."
        )
    elif "foreign key" in low or "violates foreign key" in low:
        status, message = 409, (
            "El registro referencia un elemento que no existe o que está en uso. "
            "Verificá la selección de cliente, máquina o responsable."
        )
    elif "not null" in low:
        status, message = 400, "Falta completar un campo obligatorio."
    else:
        status, message = 409, "No se pudo guardar por una restricción de integridad de datos."

    # Include the offending column when the driver tells us.
    import re
    match = re.search(r"UNIQUE constraint failed:\s*([\w.]+)", raw) or \
        re.search(r'duplicate key value violates unique constraint "([^"]+)"', raw)
    logger.warning("IntegrityError en %s %s: %s", request.method, request.url.path, raw)
    if match:
        message = f"{message} (detalle: {match.group(1)})"

    return _render_error(request, status, message)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _render_error(request, 500, "Ocurrió un error inesperado. El equipo fue notificado.")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health", include_in_schema=False)
async def health():
    """Liveness/readiness probe. Must stay exempt from auth."""
    db_ok = True
    detail = "ok"
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        detail = f"db error: {exc}"
        logger.error("Healthcheck de base de datos fallo: %s", exc)
    payload = {
        "status": "ok" if db_ok else "degraded",
        "database": detail,
        "revision": _schema_revision(),
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=payload)


# ── Catalogue / demo seeding ────────────────────────────────────────────────
def seed_catalogues(db=None) -> None:
    """Seed the auxiliary catalogues (idempotent).

    These are the lookup tables that populate the form selectors. Safe to run
    repeatedly; each block is skipped when it already has rows.
    """
    owns_session = db is None
    db = db or SessionLocal()
    try:
        if db.query(models.IndustrialSector).count() == 0:
            db.add_all([
                models.IndustrialSector(name=n) for n in (
                    "ALIMENTOS Y BEBIDAS", "AUTOMOTRIZ", "FARMACÉUTICA",
                    "METALURGIA", "QUÍMICA", "LOGÍSTICA",
                )
            ])
        if db.query(models.VisitType).count() == 0:
            db.add_all([
                models.VisitType(name=n) for n in (
                    "VISITA ESTÁNDAR", "VISITA PREMIUM", "VISITA TÉCNICA",
                )
            ])
        if db.query(models.MachineType).count() == 0:
            db.add_all([
                models.MachineType(name=n) for n in (
                    "COMPRESOR", "SECADOR", "BOMBA", "VENTILADOR", "OTRO",
                )
            ])
        if db.query(models.VisitTopic).count() == 0:
            db.add_all([
                models.VisitTopic(name=n) for n in (
                    "MANTENIMIENTO PREVENTIVO", "CAPACITACIÓN", "DIAGNÓSTICO",
                    "INSTALACIÓN", "SEGUIMIENTO",
                )
            ])
        if db.query(models.QualityTopic).count() == 0:
            db.add_all([
                models.QualityTopic(name=n) for n in (
                    "CALIDAD DE PRODUCTO", "PROCESO", "MATERIA PRIMA", "EMPAQUE",
                )
            ])
        if db.query(models.QualityAT).count() == 0:
            db.add_all([
                models.QualityAT(name=n) for n in (
                    "RESPUESTA OPORTUNA", "SOLUCIÓN EFECTIVA", "CUMPLIMIENTO DE PLAZOS",
                )
            ])
        if db.query(models.FormadoType).count() == 0:
            db.add_all([
                models.FormadoType(name=n) for n in (
                    "FLEXOGRÁFICO", "ROTOGRAVADO", "OFFSET", "DIGITAL",
                )
            ])
        if db.query(models.InferiorClosure).count() == 0:
            db.add_all([
                models.InferiorClosure(name=n) for n in (
                    "FONDO AUTOMÁTICO", "FONDO MANUAL", "SIN CIERRE",
                )
            ])
        if db.query(models.MemberSector).count() == 0:
            db.add_all([
                models.MemberSector(name=n) for n in (
                    "PRODUCCIÓN", "MANTENIMIENTO", "CALIDAD", "LOGÍSTICA",
                    "COMPRAS", "DIRECCIÓN",
                )
            ])
        db.commit()
    except Exception as exc:
        logger.error("Error sembrando catálogos: %s", exc)
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


def seed_admin(db=None, username: str = None, password: str = None, email: str = None) -> bool:
    """Create the first administrator when there are no users yet.

    Returns True when a user was created. Credentials come from the arguments or
    the ``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` / ``ADMIN_EMAIL`` environment
    variables.
    """
    import os
    from security import hash_password

    username = username or os.environ.get("ADMIN_USERNAME", "admin")
    password = password or os.environ.get("ADMIN_PASSWORD", "admin123")
    email = email or os.environ.get("ADMIN_EMAIL", "admin@crm-at.com")

    owns_session = db is None
    db = db or SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            return False
        db.add(models.User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name="Administrador",
            role="admin",
            is_active=True,
        ))
        db.commit()
        logger.info("Usuario administrador '%s' creado", username)
        return True
    except Exception as exc:
        logger.error("Error creando administrador: %s", exc)
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


def seed_demo_data(db=None) -> None:
    """Insert demonstration records (customers, machines, advisors).

    Disabled in production unless ``SEED_DEMO_DATA=true``.
    """
    owns_session = db is None
    db = db or SessionLocal()
    try:
        if db.query(models.Customer).count() == 0:
            c1 = models.Customer(
                name="Steel Metrics S.A.", plant="Planta Monterrey", industry_sector="Metalurgia",
                assigned_commercial="Carlos Pérez", city="Monterrey",
                status=CustomerStatus.CLIENTE.value,
            )
            c2 = models.Customer(
                name="AutoVanguard Corp.", plant="Sede Querétaro", industry_sector="Automotriz",
                assigned_commercial="Elena Rodríguez", city="Querétaro",
                status=CustomerStatus.CLIENTE.value,
            )
            c3 = models.Customer(
                name="Envases del Norte S.A.", plant="Planta Saltillo",
                industry_sector="Alimentos y Bebidas", assigned_commercial="Miguel Ángel",
                city="Saltillo", status=CustomerStatus.PROSPECTO.value,
            )
            db.add_all([c1, c2, c3])
            db.flush()
            db.add_all([
                models.Machine(serial_number="SN-99821-X", model="GA 37VSD", brand="Atlas Copco",
                               plant_assigned="Planta Monterrey - Línea 1", status="Operativo",
                               relevamiento_status=RelevamientoStatus.COMPLETADO.value, customer_id=c1.id),
                models.Machine(serial_number="SN-99822-X", model="ZR 300", brand="Atlas Copco",
                               plant_assigned="Planta Monterrey - Línea 2", status="Operativo",
                               relevamiento_status=RelevamientoStatus.PENDIENTE.value, customer_id=c1.id),
                models.Machine(serial_number="SN-44512-Y", model="1LE1001", brand="Siemens",
                               plant_assigned="Sede Querétaro - Nave A", status="Operativo",
                               relevamiento_status=RelevamientoStatus.EN_PROCESO.value, customer_id=c2.id),
                models.Machine(serial_number="SN-44513-Y", model="ACS580", brand="ABB",
                               plant_assigned="Sede Querétaro - Nave A", status="Mantenimiento",
                               relevamiento_status=RelevamientoStatus.PENDIENTE.value, customer_id=c2.id),
                models.Machine(serial_number="SN-77101-Z", model="FlexLine 200", brand="Bosch",
                               plant_assigned="Planta Saltillo", status="Operativo",
                               relevamiento_status=RelevamientoStatus.PENDIENTE.value, customer_id=c3.id),
            ])
        if db.query(models.TechnicalAdvisor).count() == 0:
            db.add_all([models.TechnicalAdvisor(name="ING. ROBERTO GÓMEZ"),
                        models.TechnicalAdvisor(name="ING. ALICIA TORRES")])
        if db.query(models.Designer).count() == 0:
            db.add_all([models.Designer(name="ARQ. STUDIO ALPHA"),
                        models.Designer(name="DESIGN PRO S.A.")])
        if db.query(models.CommercialAdvisor).count() == 0:
            db.add_all([models.CommercialAdvisor(name="CARLOS PÉREZ"),
                        models.CommercialAdvisor(name="ELENA RODRÍGUEZ")])
        db.commit()
    except Exception as exc:
        logger.error("Error sembrando datos demo: %s", exc)
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


# ── Router registration ─────────────────────────────────────────────────────
from routers import auth as auth_router
from routers import dashboard as dashboard_router
from routers import products as products_router
from routers import importacion as importacion_router
from routers import busqueda as busqueda_router
from routers import customers as customers_router
from routers import machinery as machinery_router
from routers import visits2 as visits2_router
from routers import relevamiento as relevamiento_router
from routers import relevamiento2 as relevamiento2_router
from routers import infraestructura as infra_router
from routers import kpis as kpis_router
from routers import control_at as control_at_router
from routers import seguimiento as seguimiento_router
from routers import configuracion as config_router
from routers import trash as trash_router
from routers import agenda as agenda_router
from routers import minutas as minutas_router
from routers import historial as historial_router

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(products_router.router)
app.include_router(importacion_router.router)
app.include_router(busqueda_router.router)
app.include_router(customers_router.router)
app.include_router(machinery_router.router)
app.include_router(visits2_router.router)
app.include_router(relevamiento_router.router)
app.include_router(infra_router.router)
app.include_router(relevamiento2_router.router)
app.include_router(kpis_router.router)
app.include_router(control_at_router.router)
app.include_router(seguimiento_router.router)
app.include_router(config_router.router)
app.include_router(trash_router.router)
app.include_router(agenda_router.router)
app.include_router(minutas_router.router)
app.include_router(historial_router.router)


# ── CLI ─────────────────────────────────────────────────────────────────────
def _cli() -> None:
    """Small management CLI: ``python main.py <command>``."""
    import argparse

    parser = argparse.ArgumentParser(description=f"{settings.app_name} - utilidades")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="Crea catálogos, el administrador inicial y datos demo opcionales")
    p_seed.add_argument("--demo", action="store_true", help="Insertar datos de demostración")
    p_seed.add_argument("--username", default=None)
    p_seed.add_argument("--password", default=None)
    p_seed.add_argument("--email", default=None)

    p_admin = sub.add_parser("create-admin", help="Crea el administrador inicial si no existe")
    p_admin.add_argument("--username", default=None)
    p_admin.add_argument("--password", default=None)
    p_admin.add_argument("--email", default=None)

    sub.add_parser("check-schema", help="Informa la revisión de esquema aplicada")

    args = parser.parse_args()

    if args.command == "check-schema":
        print(f"Revisión de esquema: {_schema_revision()}")
        return

    if args.command in ("seed", "create-admin"):
        seed_catalogues()
        created = seed_admin(username=args.username, password=args.password, email=args.email)
        if created:
            print(f"Administrador '{args.username or 'admin'}' creado.")
        else:
            print("Ya existe al menos un usuario; no se creó administrador.")
        if args.command == "seed" and getattr(args, "demo", False):
            seed_demo_data()
            print("Datos de demostración insertados.")
        return


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        _cli()
    else:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.debug,
            log_level=settings.log_level.lower(),
        )
