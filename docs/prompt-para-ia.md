# Prompt de Reconstrucción Completa — AplicaciónAT

Eres un desarrollador experto en Python, FastAPI, SQLAlchemy, Jinja2, Tailwind CSS y JavaScript vanilla. Debes reconstruir la aplicación web **AplicaciónAT** (Sistema de Gestión de Asistencia Técnica Industrial) completa desde cero, siguiendo TODAS las instrucciones, reglas de negocio, estructura, diseño y funcionalidades detalladas a continuación. No omitas ningún archivo, ruta, modelo, template o regla.

---

## 1. Stack Tecnológico

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **ORM**: SQLAlchemy 2.0 (async y sync), Alembic para migraciones
- **Base de datos**: SQLite (`sqlite:///./industrial_bi.db`) en desarrollo; PostgreSQL (vía `DATABASE_URL`) en producción
- **Seguridad**: JWT (`python-jose`), bcrypt (`passlib`), CSRF tokens, cookies firmadas
- **Frontend**: Jinja2 templates, Tailwind CSS v3, JavaScript vanilla
- **Plugins Tailwind**: `@tailwindcss/forms` (strategy: class), `@tailwindcss/container-queries`
- **Fuentes**: Google Fonts Inter (variable)
- **Iconos**: Material Symbols Rounded (Google Icons)
- **Gráficos**: Chart.js v4 (bundled como `chart.umd.min.js`)
- **Tablas dinámicas**: Tabulator v6 (bundled como `tabulator.min.js`)
- **Assets**: CSS compilado con Tailwind CLI (`npm run build:css`)
- **Dependencias Python** (`requirements.txt`):

```
fastapi==0.115.0
uvicorn[standard]
sqlalchemy~=2.0.35
python-jose[cryptography]~=3.3.0
passlib[bcrypt]~=1.7.4
bcrypt~=4.0.1
alembic~=1.13.2
pydantic~=2.9.2
pydantic-settings~=2.5.2
python-multipart~=0.0.12
jinja2~=3.1.4
aiofiles~=24.1.0
python-dateutil~=2.9.0
```

---

## 2. Estructura de Archivos

```
industrial_bi/
├── app/
│   ├── __init__.py
│   ├── main.py              # Punto de entrada, middlewares, routers
│   ├── config.py            # Config (Settings con pydantic-settings)
│   ├── database.py          # Engine, SessionLocal, Base
│   ├── models.py            # TODOS los modelos ORM
│   ├── enums.py             # Enums de estado y tipo
│   ├── security.py          # JWT, CSRF, cookies, password hash
│   ├── logger.py            # Logging setup
│   ├── utils.py             # Funciones helper
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── customers.py
│   │   ├── products.py
│   │   ├── machinery.py
│   │   ├── visits2.py
│   │   ├── relevamiento.py
│   │   ├── relevamiento2.py
│   │   ├── infraestructura.py
│   │   ├── kpis.py
│   │   ├── dashboard.py
│   │   ├── control_at.py
│   │   ├── seguimiento.py
│   │   ├── configuracion.py
│   │   ├── agenda.py
│   │   ├── minutas.py
│   │   ├── trash.py
│   │   └── ── (carpeta api/ con routers API JSON si aplica)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── customer_service.py
│   │   ├── product_service.py
│   │   ├── machine_service.py
│   │   ├── survey_service.py
│   │   ├── tracking_service.py
│   │   ├── kpi_service.py
│   │   ├── dashboard_service.py
│   │   ├── trash_service.py
│   │   ├── meeting_service.py
│   │   ├── agenda_service.py
│   │   ├── soft_delete.py      # Mixin/funciones soft-delete
│   │   ├── pagination.py       # Paginación genérica
│   │   ├── utils.py            # Validación, formateo
│   │   └── ── (schemas.py puede estar en services/ o app/)
│   ├── templates/
│   │   ├── layout.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── clientes.html
│   │   ├── nuevo_cliente.html
│   │   ├── maquinaria.html
│   │   ├── productos.html
│   │   ├── visitas2_lista.html
│   │   ├── nueva_visita2.html
│   │   ├── relevamiento.html
│   │   ├── relevamiento_ver.html
│   │   ├── nuevo_relevamiento2.html
│   │   ├── relevamiento2_lista.html
│   │   ├── relevamiento_infraestructura_form.html
│   │   ├── relevamiento_infraestructura_lista.html
│   │   ├── dashboard.html
│   │   ├── control_at.html
│   │   ├── kpis_at.html
│   │   ├── kpi_calidad.html
│   │   ├── seguimiento_plan.html
│   │   ├── agenda.html
│   │   ├── configuracion.html
│   │   ├── minutas_lista.html
│   │   ├── nueva_minuta.html
│   │   ├── trash.html
│   │   └── partials/           # Fragmentos reutilizables
│   ├── schemas/                # Schemas Pydantic
│   │   ├── __init__.py
│   │   ├── visit.py
│   │   ├── survey.py
│   │   ├── customer.py
│   │   ├── machine.py
│   │   ├── meeting.py
│   │   └── at_assignment.py
│   └── static/
│       ├── css/
│       │   ├── input.css       # Directivas Tailwind (solo 3)
│       │   ├── style.css       # TODO el CSS custom
│       │   └── fonts.css       # Import Google Fonts
│       ├── js/
│       │   ├── app.js          # Todo el JS de la app
│       │   ├── chart.umd.min.js
│       │   └── tabulator.min.js
│       └── ... (favicon, etc.)
├── tests/
│   ├── test_auth.py
│   ├── test_customers.py
│   ├── test_products.py
│   ├── test_machinery.py
│   ├── test_visits.py
│   └── test_trash.py
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/              # Migraciones
├── docs/
│   ├── funcionalidades.md
│   ├── basededatos.md
│   └── prompt-para-ia.md      # Este archivo
├── requirements.txt
├── tailwind.config.js
├── package.json
└── .gitignore
```

---

## 3. Configuración y Arranque

### `config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "AplicaciónAT"
    DATABASE_URL: str = "sqlite:///./industrial_bi.db"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas
    SESSION_EXPIRE_MINUTES: int = 30
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"

settings = Settings()
```

### `database.py`

- `engine` creado con `create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})` para SQLite
- `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`
- `Base = declarative_base()`
- `get_db()` como generador de sesiones

### `main.py`

- FastAPI app con `title="AplicaciónAT"`
- **Middlewares** (en orden):
  1. `CORSMiddleware` (allow all origins en desarrollo)
  2. `SecurityHeadersMiddleware` (clase custom que agrega: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: geolocation=(), microphone=(), camera=()`)
  3. `SessionMiddleware` (starlette, `secret_key=settings.SECRET_KEY`, `max_age=3600`, `same_site="lax"`, `https_only=False`)
- **Mounts**:
  - `/static` → `StaticFiles(directory="app/static")`
- **Exception handlers**:
  - `404.html` (desde templates)
  - `403.html`
  - `405.html`
- **Filtro CSRF automático**: un middleware o decorador que excluye GET/HEAD/OPTIONS y ciertas rutas (login, register). Para rutas POST no-JSON, se espera `_csrf_token` en form data. Para rutas JSON, se espera `X-CSRF-Token` en header. El token CSRF se genera con `secrets.token_hex(32)` y se almacena en `request.session`.
- **Montaje de routers**: todos los routers de `app/routers/`
- **Startup**: usar `@asynccontextmanager` con parámetro `lifespan=` en la app FastAPI (patrón moderno, no `@app.on_event("startup")`). En el startup: crear tablas si no existen (`Base.metadata.create_all`) y crear usuario admin por defecto.

---

## 4. Modelos de Datos (models.py)

Usar SQLAlchemy declarative base. Todos los modelos deben tener soft-delete excepto User y TrashItem.

### 4.1 Mixins

#### `TimestampMixin`
```python
created_at = Column(DateTime, default=datetime.utcnow)
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### `SoftDeleteMixin`
```python
is_active = Column(Boolean, default=True)
inactivation_reason = Column(String(255), nullable=True)
inactivated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
inactivated_at = Column(DateTime, nullable=True)
```

#### `BaseCatalogMixin(TimestampMixin, SoftDeleteMixin)`
Clase abstracta para tablas de catálogo: `id` (PK autoincrement), `name` (String 255, unique), más los campos de ambos mixins.

```python
class BaseCatalogMixin(TimestampMixin, SoftDeleteMixin):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
```

### 4.2 Tablas de Catálogo (heredan de `BaseCatalogMixin`)

Cada una en su propia clase con `__tablename__`. 16 tablas:

1. **TechnicalAdvisor**
2. **Designer**
3. **CommercialAdvisor**
4. **IndustrialSector** (name = sector, nullable)
5. **MachineType**
6. **VisitTopic** (name = nombre_tema)
7. **FormadoType** (name = tipo_formado)
8. **InferiorClosure** (name = cierre_inferior)
9. **ClientName** (name = nombre_cliente_at)
10. **PlantName** (name = nombre_planta)
11. **VisitType** (name = tipo_visita)
12. **DistributorPlant** (name = planta_distribuidor)
13. **QualityTopic** (name = nombre_tema_calidad)
14. **QualityAT** (name = nombre_at_calidad)
15. **ContactName** (name = nombre_contacto) — catálogo de nombres de contacto para dropdown "Nombre Completo" del equipo del cliente
16. **MemberSector** (name = nombre_sector) — catálogo de sectores/departamentos para dropdown del equipo del cliente

Relaciones:
- `QualityAT` tiene `FK quality_topic_id → QualityTopic.id`
- `TechnicalSurvey.quality_at_id` → `QualityAT.id`
- `TechnicalSurveyV2.quality_at_id` → `QualityAT.id`

### 4.3 User

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_admin = Column(Boolean, default=False)
```

### 4.4 Customer

```python
class Customer(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    empresa = Column(String(100), nullable=True)
    industry_sector_id = Column(Integer, ForeignKey("industrial_sectors.id"), nullable=True)
    contacto = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    telefono = Column(String(50), nullable=True)
    direccion = Column(String(200), nullable=True)

    products = relationship("Product", back_populates="customer", cascade="all, delete-orphan")
    machines = relationship("Machine", back_populates="customer", cascade="all, delete-orphan")
    visits = relationship("TechnicalVisit2", back_populates="customer")
    surveys = relationship("TechnicalSurvey", back_populates="customer")
    surveys_v2 = relationship("TechnicalSurveyV2", back_populates="customer")
```

### 4.5 Product

```python
class Product(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(100), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    codigo = Column(String(50), nullable=True)
    descripcion = Column(String(500), nullable=True)

    customer = relationship("Customer", back_populates="products")
```

### 4.6 Machine

```python
class Machine(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "machines"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    machine_name = Column(String(100), nullable=False)
    machine_type_id = Column(Integer, ForeignKey("machine_types.id"), nullable=True)

    customer = relationship("Customer", back_populates="machines")
    machine_type = relationship("MachineType")
```

### 4.7 TechnicalVisit2 (Visitas Técnicas)

```python
class TechnicalVisit2(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "technical_visits_2"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha_visita = Column(Date, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    technical_advisor_id = Column(Integer, ForeignKey("technical_advisors.id"), nullable=True)
    designer_id = Column(Integer, ForeignKey("designers.id"), nullable=True)
    commercial_advisor_id = Column(Integer, ForeignKey("commercial_advisors.id"), nullable=True)
    topic_id = Column(Integer, ForeignKey("visit_topics.id"), nullable=True)
    objective = Column(String(50), nullable=True)           # "Nuevo", "Repetitivo", "Proyecto"
    product_type = Column(String(50), nullable=True)         # "Formado", "Cierre", "Empaque", "Sellado"
    codigo_muestra = Column(String(100), nullable=True)
    product_name = Column(String(200), nullable=True)
    forma = Column(String(100), nullable=True)
    plant = Column(String(50), nullable=True)                # "Planta 1", "Planta 2" o texto libre
    maquina = Column(Text, nullable=True)                    # JSON serializado
    turno = Column(String(50), nullable=True)
    formado_type_id = Column(Integer, ForeignKey("formado_types.id"), nullable=True)
    inferior_closure_id = Column(Integer, ForeignKey("inferior_closures.id"), nullable=True)

    # Detalles de la visita → Almacenados como JSON (Text)
    materia_prima = Column(Text, nullable=True)              # JSON array
    parametros_proceso = Column(Text, nullable=True)         # JSON array
    producto_terminado = Column(Text, nullable=True)         # JSON array
    control_calidad = Column(Text, nullable=True)            # JSON array
    observaciones = Column(Text, nullable=True)              # JSON array o texto
    plan_accion = Column(Text, nullable=True)                # JSON array
    acciones = Column(Text, nullable=True)                   # JSON array

    # Plan de acción con seguimiento
    action_plan = Column(Text, nullable=True)                # JSON array con seguimiento integrado

    # Fotos
    fotos = Column(Text, nullable=True)                     # JSON array de rutas/nombres

    # Firma
    firma_cliente = Column(Text, nullable=True)              # Base64 o descripción
    firma_asesor = Column(Text, nullable=True)               # Base64 o descripción
    firma_fecha = Column(DateTime, nullable=True)

    # Relación con seguimiento
    tracking_items = relationship("ActionPlanTracking", back_populates="visit", cascade="all, delete-orphan")

    customer = relationship("Customer", back_populates="visits")
    topic = relationship("VisitTopic")
    technical_advisor = relationship("TechnicalAdvisor")
    designer = relationship("Designer")
    commercial_advisor = relationship("CommercialAdvisor")
    formado_type = relationship("FormadoType")
    inferior_closure = relationship("InferiorClosure")
```

**Regla de negocio**: el formulario `nueva_visita2.html` tiene 17 tablas editables (arrays). Cada fila de tabla es un dict con columnas. Se serializan como JSON arrays en los campos Text. El campo `action_plan` contiene objetos con `{accion, responsable, fecha_compromiso, estado, fecha_cierre, observaciones}`.

### 4.8 TechnicalSurvey (Relevamiento Técnico — original)

```python
class TechnicalSurvey(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "technical_surveys"
    id = Column(Integer, primary_key=True, index=True)
    fecha_relevamiento = Column(Date, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    technical_advisor_id = Column(Integer, ForeignKey("technical_advisors.id"), nullable=True)
    designer_id = Column(Integer, ForeignKey("designers.id"), nullable=True)
    quality_at_id = Column(Integer, ForeignKey("quality_at.id"), nullable=True)
    topic = Column(String(100), nullable=True)

    # Campos JSON similares a TechnicalVisit2
    materia_prima = Column(Text, nullable=True)
    parametros_proceso = Column(Text, nullable=True)
    producto_terminado = Column(Text, nullable=True)
    control_calidad = Column(Text, nullable=True)
    observaciones = Column(Text, nullable=True)
    plan_accion = Column(Text, nullable=True)
    acciones = Column(Text, nullable=True)
    action_plan = Column(Text, nullable=True)

    # Foto del equipo actual
    foto_equipo_actual = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="surveys")
    quality_at = relationship("QualityAT")
    technical_advisor = relationship("TechnicalAdvisor")
    designer = relationship("Designer")
```

### 4.9 TechnicalSurveyV2 (Relevamiento Técnico v2)

```python
class TechnicalSurveyV2(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "technical_surveys_v2"
    id = Column(Integer, primary_key=True, index=True)
    fecha_relevamiento = Column(Date, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    technical_advisor_id = Column(Integer, ForeignKey("technical_advisors.id"), nullable=True)
    designer_id = Column(Integer, ForeignKey("designers.id"), nullable=True)
    quality_at_id = Column(Integer, ForeignKey("quality_at.id"), nullable=True)
    topic = Column(String(100), nullable=True)
    product_type = Column(String(50), nullable=True)
    plant = Column(String(50), nullable=True)
    machine_name = Column(String(100), nullable=True)

    materia_prima = Column(Text, nullable=True)
    parametros_proceso = Column(Text, nullable=True)
    producto_terminado = Column(Text, nullable=True)
    control_calidad = Column(Text, nullable=True)
    observaciones = Column(Text, nullable=True)
    plan_accion = Column(Text, nullable=True)
    acciones = Column(Text, nullable=True)
    action_plan = Column(Text, nullable=True)
    fotos = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="surveys_v2")
    quality_at = relationship("QualityAT")
    technical_advisor = relationship("TechnicalAdvisor")
    designer = relationship("Designer")
```

### 4.10 InfrastructureSurvey (Relevamiento de Infraestructura)

```python
class InfrastructureSurvey(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "infrastructure_surveys"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    technical_advisor_id = Column(Integer, ForeignKey("technical_advisors.id"), nullable=True)
    fecha_relevamiento = Column(Date, nullable=False)

    # Datos generales
    nombre_cliente_at = Column(String(255), nullable=True)       # FK lógica a ClientName
    nombre_planta = Column(String(255), nullable=True)           # FK lógica a PlantName
    direccion = Column(Text, nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    tipo_visita_id = Column(Integer, ForeignKey("visit_types.id"), nullable=True)
    planta_distribuidor_id = Column(Integer, ForeignKey("distributor_plants.id"), nullable=True)
    tipo_visita_otra = Column(String(100), nullable=True)

    # Personal
    personal_llave = Column(Text, nullable=True)                 # JSON
    personal_mantenimiento = Column(Text, nullable=True)         # JSON
    personal_produccion = Column(Text, nullable=True)            # JSON

    # Datos de la máquina
    datos_maquina = Column(Text, nullable=True)                  # JSON

    customer = relationship("Customer")
    technical_advisor = relationship("TechnicalAdvisor")
    visit_type = relationship("VisitType")
    distributor_plant = relationship("DistributorPlant")
```

### 4.11 ATAssignment (Asignación AT)

```python
class ATAssignment(Base, TimestampMixin):
    __tablename__ = "at_assignments"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(255), nullable=False)          # NO unique (SCD Tipo 2)
    technical_advisor_id = Column(Integer, ForeignKey("technical_advisors.id"), nullable=True)
    designer_id = Column(Integer, ForeignKey("designers.id"), nullable=True)
    commercial_advisor_id = Column(Integer, ForeignKey("commercial_advisors.id"), nullable=True)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=True)                      # NULL = vigente

    # Indicadores de visita
    visit_goal = Column(Integer, default=0)
    visits_completed = Column(Integer, default=0)
    visits_pending = Column(Integer, default=0)

    technical_advisor = relationship("TechnicalAdvisor")
    designer = relationship("Designer")
    commercial_advisor = relationship("CommercialAdvisor")
```

**Regla de negocio**: `customer_name` NO es unique (permite SCD Tipo 2). Para cada cliente, SOLO una asignación debe tener `valid_to IS NULL` (vigente). Al crear/actualizar una asignación para un cliente existente, se debe cerrar la anterior (set `valid_to = date(created_at)` o fecha actual).

### 4.12 ActionPlanTracking (Seguimiento de Plan de Acción)

```python
class ActionPlanTracking(Base, TimestampMixin):
    __tablename__ = "action_plan_tracking"
    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("technical_visits_2.id"), nullable=False)
    accion = Column(String(500), nullable=False)
    responsable = Column(String(200), nullable=True)
    fecha_compromiso = Column(Date, nullable=True)
    estado = Column(String(50), default="Pendiente")            # Pendiente, En Progreso, Completada, Cancelada
    fecha_cierre = Column(Date, nullable=True)
    observaciones = Column(Text, nullable=True)
    prioridad = Column(String(20), default="Media")             # Alta, Media, Baja

    visit = relationship("TechnicalVisit2", back_populates="tracking_items")
```

### 4.13 MeetingMinutes (Minutas)

```python
class MeetingMinutes(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "meeting_minutes"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    technical_advisor_id = Column(Integer, ForeignKey("technical_advisors.id"), nullable=True)
    fecha_minuta = Column(Date, nullable=False)
    tema = Column(String(200), nullable=True)
    ubicacion = Column(String(200), nullable=True)
    participantes = Column(Text, nullable=True)                 # JSON array
    puntos_tratados = Column(Text, nullable=True)               # JSON array
    compromisos = Column(Text, nullable=True)                   # JSON array
    prooximos_pasos = Column(Text, nullable=True)               # JSON array

    customer = relationship("Customer")
    technical_advisor = relationship("TechnicalAdvisor")
```

### 4.14 TrashItem (Papelera de reciclaje — soft delete global)

```python
class TrashItem(Base, TimestampMixin):
    __tablename__ = "trash_items"
    id = Column(Integer, primary_key=True, index=True)
    original_table = Column(String(100), nullable=False)        # Nombre de la tabla original
    original_id = Column(Integer, nullable=False)               # ID del registro original
    original_data = Column(Text, nullable=False)                # JSON completo del registro
    deleted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deletion_reason = Column(String(255), nullable=False)
```

Cuando se elimina un registro (soft-delete), se guarda una copia JSON en TrashItem para posible restauración.

---

## 5. Enums (enums.py)

```python
from enum import Enum

class VisitObjective(str, Enum):
    NUEVO = "Nuevo"
    REPETITIVO = "Repetitivo"
    PROYECTO = "Proyecto"

class ProductType(str, Enum):
    FORMADO = "Formado"
    CIERRE = "Cierre"
    EMPAQUE = "Empaque"
    SELLADO = "Sellado"

class PlantType(str, Enum):
    PLANTA_1 = "Planta 1"
    PLANTA_2 = "Planta 2"

class TrackingStatus(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROGRESO = "En Progreso"
    COMPLETADA = "Completada"
    CANCELADA = "Cancelada"

class Priority(str, Enum):
    ALTA = "Alta"
    MEDIA = "Media"
    BAJA = "Baja"

class ImpactLevel(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"
```

---

## 6. Seguridad (security.py)

- **JWT**: Usar `python-jose` con `jwt.encode`/`jwt.decode`. Payload: `{"sub": username, "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)}`. Algoritmo HS256.
- **Password hashing**: Usar `passlib.context.CryptContext(schemes=["bcrypt"])`.
- **CSRF**: Generar token con `secrets.token_hex(32)`. Guardar en `request.session["csrf_token"]`. En cada form POST (no GET), incluir campo oculto `_csrf_token`. El middleware CSRF verifica que coincida. Para fetch API, enviar en header `X-CSRF-Token`.
- **Autenticación**: Cookie `session` con `request.session["user"] = {"username": ..., "id": ...}`. Para rutas JSON, verificar header `Authorization: Bearer <token>`. Para HTML, redirigir a login si no hay sesión.
- **Decorador `login_required`**: función que verifica `request.session.get("user")`. Si no existe, redirige a `/login?next={path}`.
- **Decorador `admin_required`**: verifica `request.session["user"].get("is_admin")`.
- **Rutas públicas**: `/login`, `/register`, `/static/*`
- El usuario admin por defecto se crea en startup si no existe.

---

## 7. Rutas (Routers)

Cada router usa `APIRouter(prefix=..., tags=...)` y depende de `get_db()` para la sesión. Todos los modelos se importan de `app.models`.

### 7.1 auth.py — `/auth`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/login` | Formulario login |
| POST | `/login` | Validar credenciales, crear sesión |
| GET | `/register` | Formulario registro (solo admin) |
| POST | `/register` | Crear usuario |
| GET | `/logout` | Cerrar sesión |
| GET | `/me` | Perfil del usuario logueado |

### 7.2 customers.py — `/customers`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista de clientes (con paginación, búsqueda, filtro industria) |
| GET | `/new` | Formulario nuevo cliente |
| POST | `/new` | Crear cliente |
| GET | `/{id}` | Ver detalle cliente (con productos, máquinas, visitas) |
| GET | `/{id}/edit` | Formulario editar cliente |
| POST | `/{id}/edit` | Actualizar cliente |
| POST | `/{id}/delete` | Soft-delete cliente (con razón) |
| GET | `/api/list` | API JSON: lista clientes activos (para selects) |
| GET | `/api/with-relations` | API JSON: clientes con máquinas y productos |

### 7.3 products.py — `/products`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista de productos |
| GET | `/new` | Formulario nuevo producto |
| POST | `/new` | Crear producto |
| GET | `/{id}/edit` | Formulario editar producto |
| POST | `/{id}/edit` | Actualizar producto |
| POST | `/{id}/delete` | Soft-delete producto |
| GET | `/by-customer/{customer_id}` | API JSON: productos por cliente |

### 7.4 machinery.py — `/machinery`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista de máquinas |
| GET | `/new` | Formulario nueva máquina |
| POST | `/new` | Crear máquina |
| GET | `/{id}/edit` | Formulario editar máquina |
| POST | `/{id}/edit` | Actualizar máquina |
| POST | `/{id}/delete` | Soft-delete máquina |
| GET | `/by-customer/{customer_id}` | API JSON: máquinas por cliente |

### 7.5 visits2.py — `/visits`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista de visitas (con filtros: cliente, fecha desde/hasta, tema) |
| GET | `/new` | Formulario nueva visita |
| POST | `/new` | Crear visita (procesa 17 tablas JSON, action_plan, fotos) |
| GET | `/{id}` | Ver detalle visita (renderiza tablas JSON) |
| GET | `/{id}/edit` | Formulario editar visita |
| POST | `/{id}/edit` | Actualizar visita |
| POST | `/{id}/delete` | Soft-delete visita |
| GET | `/api/list` | API JSON: visitas con filtros (para dashboard/agenda) |
| POST | `/api/upload-photo` | Subir foto (guarda en `static/uploads/`) |

### 7.6 relevamiento.py — `/relevamiento`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista de relevamientos técnicos |
| GET | `/new` | Formulario nuevo relevamiento |
| POST | `/new` | Crear relevamiento |
| GET | `/{id}` | Ver detalle |
| GET | `/{id}/edit` | Editar |
| POST | `/{id}/edit` | Actualizar |
| POST | `/{id}/delete` | Soft-delete |

### 7.7 relevamiento2.py — `/relevamiento2`

Igual que relevamiento.py pero para `TechnicalSurveyV2`. Incluye foto de equipo actual.

### 7.8 infraestructura.py — `/infraestructura`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista |
| GET | `/new` | Formulario nuevo |
| POST | `/new` | Crear |
| GET | `/{id}` | Ver |
| GET | `/{id}/edit` | Editar |
| POST | `/{id}/edit` | Actualizar |
| POST | `/{id}/delete` | Soft-delete |

### 7.9 kpis.py — `/kpis`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/at` | KPIs de Asistencia Técnica (asignaciones) |
| GET | `/calidad` | KPIs de Calidad (con filtros y gráficos) |
| GET | `/api/kpi-calidad` | API JSON: datos para gráficos de calidad |

### 7.10 dashboard.py — `/dashboard`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Dashboard principal con KPIs globales |

### 7.11 control_at.py — `/control-at`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Control de AT (asignaciones vs visitas realizadas) |
| GET | `/api/data` | API JSON: datos de control AT |

### 7.12 seguimiento.py — `/seguimiento`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/plan` | Seguimiento de plan de acción |
| POST | `/plan/{id}/update-status` | Actualizar estado de una acción |

### 7.13 configuracion.py — `/configuracion`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Página de configuración (catálogos) |
| POST | `/catalogo/{nombre}/add` | Agregar item a catálogo |
| POST | `/catalogo/{nombre}/edit/{id}` | Editar item |
| POST | `/catalogo/{nombre}/delete/{id}` | Soft-delete item |

Catálogos editables: technical_advisors, designers, commercial_advisors, industrial_sectors, machine_types, visit_topics, formado_types, inferior_closures, client_names, plant_names, visit_types, distributor_plants, quality_topics, quality_at.

### 7.14 agenda.py — `/agenda`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Calendario mensual con visitas como eventos |
| GET | `/api/events` | API JSON: visitas del mes (para calendario JS) |

### 7.15 minutas.py — `/minutas`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista de minutas |
| GET | `/new` | Formulario nueva minuta |
| POST | `/new` | Crear minuta |
| GET | `/{id}` | Ver detalle |
| GET | `/{id}/edit` | Editar |
| POST | `/{id}/edit` | Actualizar |
| POST | `/{id}/delete` | Soft-delete |

### 7.16 trash.py — `/trash`

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Lista de elementos eliminados (papelera) |
| POST | `/{id}/restore` | Restaurar elemento a su tabla original |
| POST | `/cleanup` | Vaciar papelera (hard delete todos) |

---

## 8. Servicios (Capa de Negocio)

Cada servicio encapsula la lógica de negocio. Patrón: función que recibe `db: Session` y parámetros.

### 8.1 soft_delete.py

Función `soft_delete(db, model_instance, reason, user_id)`:
- Set `is_active = False`
- Set `inactivation_reason = reason`
- Set `inactivated_by_id = user_id`
- Set `inactivated_at = datetime.utcnow()`
- Guardar copia en `TrashItem` (JSON serializado de todos los campos)
- Hace commit

Función `restore_from_trash(db, trash_item_id)`:
- Lee TrashItem
- Restaura registro original: `is_active = True`, `inactivation_reason = None`, `inactivated_by_id = None`, `inactivated_at = None`
- Elimina TrashItem

### 8.2 pagination.py

Función `paginate(query, page, per_page=20)`:
- Retorna `{"items": [...], "total": count, "page": page, "pages": math.ceil(total/per_page), "per_page": per_page}`

### 8.3 customer_service.py

- `get_customers(db, search, sector_id, page)`: lista paginada con filtros
- `get_customer(db, customer_id)`: detalle
- `create_customer(db, data)`: crear
- `update_customer(db, customer_id, data)`: actualizar
- `delete_customer(db, customer_id, reason, user_id)`: soft-delete
- `get_active_customers(db)`: lista JSON para selects

### 8.4 product_service.py

- `get_products(db, customer_id)`
- `create_product(db, data)`
- `update_product(db, product_id, data)`
- `delete_product(db, product_id, reason, user_id)`

### 8.5 machine_service.py

- `get_machines(db, customer_id)`
- `create_machine(db, data)`
- `update_machine(db, machine_id, data)`
- `delete_machine(db, machine_id, reason, user_id)`

### 8.6 survey_service.py

Maneja `TechnicalSurvey` y `TechnicalSurveyV2`:
- CRUD completo
- Serialización/deserialización de campos JSON

### 8.7 kpi_service.py

- `get_at_assignments(db, filters)`: lista asignaciones AT (SCD Tipo 2)
- `create_at_assignment(db, data)`: crear asignación, cierra la anterior si existe
- `update_at_assignment(db, id, data)`: actualizar
- `delete_at_assignment(db, id)`: hard delete (no soft-delete)
- `get_kpi_calidad_data(db, year, month, at_ids, client_ids, topic_ids, impact, product_type, plant)`: datos agregados para KPIs de calidad

### 8.8 dashboard_service.py

- `get_dashboard_kpis(db)`: retorna dict con:
  - `total_customers`, `total_visits`, `total_machines`, `total_minutas`
  - `visits_by_month` (últimos 12 meses)
  - `visits_goal` y `visits_progress` (suma de visit_goal y visits_completed de ATAssignments vigentes)
  - `kpi_calidad_summary`
  - `recent_visits` (últimas 5)

### 8.9 tracking_service.py

- `get_tracking_items(db, visit_id)`
- `update_tracking_status(db, item_id, status)`: cambia estado, si es "Completada" set `fecha_cierre = today`

### 8.10 trash_service.py

- `get_trash_items(db, page)`
- `restore_item(db, item_id)`
- `cleanup_all(db)`: hard delete todos

### 8.11 agenda_service.py

- `get_month_events(db, year, month)`: retorna visitas del mes como eventos `{title, start, end, url, color, status}`

### 8.12 meeting_service.py

- CRUD completo de MeetingMinutes
- Serialización/deserialización de campos JSON (participantes, puntos_tratados, compromisos, prooximos_pasos)

---

## 9. Templates HTML

### 9.1 layout.html (base)

- **DOCTYPE**: HTML5, lang="es"
- **Head**: meta charset, viewport, title dinámico (block `title`), Google Fonts Inter, Material Symbols Rounded, Tailwind output (`style.css`), fonts.css
- **Body**: estructura con `id="app"` que contiene:
  - **Sidebar** (barra lateral izquierda, 240px en desktop, oculta en mobile con overlay):
    - Logo/nombre app
    - Usuario logueado (nombre + rol)
    - Enlaces: Dashboard, Clientes, Productos, Maquinaria, Visitas, Relevamiento, Relevamiento v2, Infraestructura, Control AT, KPIs (AT + Calidad), Seguimiento, Agenda, Minutas, Configuración, Papelera
    - Botón "Cerrar sesión"
  - **Header** superior: título de página (block `header`), botón hamburguesa para mobile, toggle dark mode, search
  - **Main content** (block `content`)
  - **Toast container** (fijo, esquina superior derecha, para notificaciones)
- **Footer scripts**: app.js, chart.umd.min.js, tabulator.min.js, block `scripts`
- **Tema oscuro**: detectar preferencia del sistema (`prefers-color-scheme: dark`), toggle manual con botón, persistir en `localStorage`, clase `dark` en `<html>`

### 9.2 login.html

- Formulario centrado (tarjeta glassmorphism), fondo con gradiente (dark mode compatible)
- Campos: username, password
- Botón "Iniciar Sesión" con spinner
- Enlace "Registrarse" (solo visible si no hay usuarios)

### 9.3 register.html

- Formulario centrado, mismos campos + email + full_name
- Solo accesible por admin o si no hay usuarios

### 9.4 clientes.html (lista)

- Sidebar layout
- Botón "Nuevo Cliente"
- Tabla de clientes con: Nombre, Empresa, Sector, Contacto, Email, Teléfono, Acciones (Ver, Editar, Eliminar)
- Paginación
- Filtro por búsqueda y sector industrial
- Cada fila: hover highlight, acciones con iconos Material Symbols

### 9.5 nuevo_cliente.html / clientes.html (edición modal)

- Formulario con validación
- Campos: customer_name, empresa, industry_sector (select desde catálogo), contacto, email, telefono, direccion
- **Equipo del cliente** (tabla dinámica):
  - Nombre Completo (`<select class="team-name-select">` + quick-add desde catálogo `ContactName`)
  - Reporta a (`<select class="team-reports-select">` — opciones del mismo equipo del cliente)
  - Sector/Departamento (`<select class="team-sector-select">` + quick-add desde catálogo `MemberSector`)
  - Cargo/Función (texto en mayúsculas forzadas vía JS `oninput`)
  - Teléfono
  - Botón eliminar fila
- Botón "+" agrega fila, botón "✕" la elimina
- Botón guardar con confirmación

### 9.5b organigrama.html

- Página `/organigrama` con selector de cliente (dropdown poblado de clientes activos)
- Al seleccionar un cliente, carga vía `GET /api/cliente-team/{customer_id}` los miembros del `client_team` con `reports_to` y `sector`
- Renderiza árbol jerárquico agrupado por Sector/Departamento (encabezado por sector, luego miembros)
- Miembros sin `reports_to` son raíces del árbol; los que reportan a alguien se anidan jerárquicamente
- Miembros sin sector se agrupan bajo "SIN SECTOR"

### 9.6 maquinaria.html

- Lista + formulario nuevo en misma página (o modal)
- Tabla: Máquina, Cliente, Tipo Máquina, Acciones
- Filtro por cliente

### 9.7 productos.html

- Igual que maquinaria, para productos
- Tabla: Producto, Cliente, Código, Descripción, Acciones

### 9.8 nueva_visita2.html (LA MÁS COMPLEJA)

Formulario de visita técnica con 17 secciones editables en tablas:

1. **Encabezado**: Fecha, Cliente (select), Asesor Técnico (select), Diseñador (select), Asesor Comercial (select), Tema (select), Objetivo (radio: Nuevo/Repetitivo/Proyecto), Tipo Producto (radio: Formado/Cierre/Empaque/Sellado)
2. **Código Muestra** (text input)
3. **Nombre Producto** (text input)
4. **Forma** (text input)
5. **Planta** (radio: Planta 1/Planta 2 + input "otra")
6. **Máquina** (select dinámico según cliente)
7. **Turno** (text input)
8. **Tipo Formado** (select)
9. **Cierre Inferior** (select)
10. **Materia Prima** (tabla: columna1, columna2, columna3, columna4, columna5) → filas editables con botón +/-
11. **Parámetros de Proceso** (tabla: parámetro, valor, unidad, observaciones)
12. **Producto Terminado** (tabla: columna1, columna2, columna3, columna4, columna5)
13. **Control de Calidad** (tabla: columna1, columna2, columna3, columna4, columna5)
14. **Observaciones** (tabla: columna1, columna2, columna3, columna4)
15. **Plan de Acción** (tabla: acción, responsable, fecha compromiso, estado, fecha cierre, observaciones) → cada fila genera un `ActionPlanTracking`
16. **Acciones** (tabla: ET, ACCIÓN, RESPONSABLE, PLAZO) → sincronizada con `action_plan_tracking` vía `sync_action_plan()`
17. **Fotos**: subida múltiple con preview, drag & drop, eliminar

Secciones 10-17: cada una es una tabla HTML donde:
- El usuario agrega filas con botón "Agregar fila"
- Elimina filas con botón ✕
- Cada celda es un `<input>` o `<textarea>` editable
- Al guardar, se serializa TODO a JSON y se envía como campos separados (`materia_prima`, `parametros_proceso`, etc.)

**Al final del formulario**: Firma digital (canvas para dibujar firma del cliente y del asesor).

### 9.9 visitas2_lista.html

- Tabla de visitas con: Fecha, Cliente, Asesor, Tema, Objetivo, Acciones (Ver/Editar/Eliminar)
- Filtros: cliente (select), fecha desde/hasta (date inputs), tema (select)
- Paginación

### 9.10 relevamiento.html, relevamiento_ver.html, nuevo_relevamiento2.html, relevamiento2_lista.html

- Similares a visitas pero para relevamientos técnicos
- `relevamiento_ver.html` muestra detalle con tablas de datos JSON renderizadas como HTML

### 9.11 relevamiento_infraestructura_form.html

- Formulario de infraestructura con secciones:
  - Datos generales (cliente, asesor, fecha, nombre_cliente_at, nombre_planta, dirección, teléfono, email, tipo_visita, planta_distribuidor)
  - Personal (tablas editables: personal_llave, personal_mantenimiento, personal_producción)
  - Datos de máquina (tabla editable)

### 9.12 dashboard.html

Panel principal con tarjetas KPI:
- **Clientes**: total clientes activos
- **Visitas**: total visitas + barra de progreso (visitas realizadas / meta)
- **Máquinas**: total máquinas
- **Minutas**: total minutas
- **Gráfico de tendencia**: visits_by_month (bar chart con Chart.js, últimos 12 meses)
- **Últimas visitas**: tabla de las últimas 5 visitas
- **Resumen KPIs Calidad** (mini)

Filtros en dashboard: fecha_desde, fecha_hasta, tema, impacto, tipo_producto, planta.

### 9.13 control_at.html

- Tabla de asignaciones AT vs visitas realizadas
- KPIs: Total Asignaciones, Con Visitas, Sin Visitas, % Cobertura
- Filtros: año, asesor, mes
- Cada fila expandible: al hacer clic, muestra visitas de ese cliente

### 9.14 kpis_at.html

- KPIs de Asistencia Técnica
- Tabla de asignaciones con indicadores
- Gráficos de cobertura

### 9.15 kpi_calidad.html

- **Punto 7 — Asistencia Técnica**: gráfico de barras horizontales (indexAxis: 'y') con colores individuales por barra (paleta de 13 colores vía `barColors`)
- Contador de registros totales (incluye todas las filas, no solo top 8)
- **Filtros**: Año, Mes, AT, Cliente, Tema, Tipo Producto, Planta — formulario GET con recarga de página y headers `Cache-Control: no-cache`
- Link "Limpiar" para resetear filtros
- Adaptación a tema oscuro: `getChartColors()` y listener `themechange` que actualiza colores del chart

### 9.16 seguimiento_plan.html

- Tabla de acciones de plan de acción con filtros
- Cada acción: editable en línea (cambiar estado, agregar fecha cierre)
- Botones: "Marcar Completada", "En Progreso", "Cancelar"

### 9.17 agenda.html

- Calendario mensual (grid CSS, no librería externa)
- Cada visita es un "evento" en el día correspondiente
- Color por estado/tema
- Al hacer clic en evento → link al detalle de la visita
- Navegación entre meses (← →)

### 9.18 minutas_lista.html

- Tabla de minutas: Fecha, Cliente, Tema, Asesor, Acciones
- Paginación

### 9.19 nueva_minuta.html

- Formulario con: cliente, asesor, fecha, tema, ubicación
- Participantes (tabla editable con nombre, cargo, email)
- Puntos Tratados (tabla editable: tema, descripción, responsable)
- Compromisos (tabla editable: compromiso, responsable, fecha)
- Próximos Pasos (tabla editable: paso, responsable, fecha)

### 9.20 configuracion.html

- Secciones para cada catálogo (14 en total)
- Cada sección: lista de items con botón + y editar/eliminar inline
- Modal simple para agregar/editar

### 9.21 trash.html

- Tabla de elementos eliminados
- Columnas: Tabla original, ID, Fecha eliminación, Eliminado por, Razón, Acciones (Restaurar)
- Botón "Vaciar Papelera" con confirmación

---

## 10. Frontend (JS, CSS, Tailwind)

### 10.1 Tailwind Config (`tailwind.config.js`)

```javascript
module.exports = {
  content: ["./app/templates/**/*.html"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#1a57db",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
        background: {
          DEFAULT: "#f8fafc",
          dark: "#0f172a",
        },
        surface: {
          DEFAULT: "#ffffff",
          dark: "#1e293b",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms")({ strategy: "class" }),
    require("@tailwindcss/container-queries"),
  ],
};
```

### 10.2 input.css (solo 3 directivas)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 10.3 fonts.css

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,100..900&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
```

### 10.4 style.css (CSS custom)

- **Animaciones**: `@keyframes fadeIn` (opacity 0→1), `@keyframes zoomIn` (scale 0.95→1)
- **Clases de animación**: `.animate-fade-in`, `.animate-zoom-in`
- **Glassmorphism**: `.glass` (background: rgba(255,255,255,0.7), backdrop-filter: blur(20px), border: 1px solid rgba(255,255,255,0.3))
- **Dark mode glass**: `.dark .glass` (background: rgba(30,41,59,0.7), border: 1px solid rgba(255,255,255,0.1))
- **Scrollbar custom**: `::-webkit-scrollbar` (width 6px, thumb: primary-600/20 → hover: primary-600/40)
- **Selection**: `::selection` (background primary-600, text white)
- **Focus ring**: `.focus-ring` (box-shadow con primary-600/50)
- **Print styles**: `@media print` (hide sidebar, header, toasts; show content full width)
- **Transiciones**: transiciones suaves en hover/focus para inputs, botones, tarjetas

### 10.5 app.js (JavaScript)

**Toast System**:
```javascript
function showToast(message, type = "success") {
  // type: success, error, warning, info
  // Crea toast con icono Material Symbol, mensaje, barra de progreso
  // Se auto-destruye después de 4 segundos
  // Animación slide-in desde derecha
}
```

**Helper Functions**:
```javascript
function escapeHtml(str) { /* escapa HTML entities */ }
function setHTML(el, html) { /* asigna innerHTML escapado */ }

// Select dinámicos: cuando cambia cliente, actualizar máquinas y productos
// Ejemplo: $("#customer_id").change(() => fetch("/machinery/by-customer/" + id))
```

**Theme Toggle**:
```javascript
function toggleTheme() {
  // Alterna clase 'dark' en <html>
  // Cambia icono (dark_mode ↔ light_mode)
  // Guarda en localStorage
}
```

**Sidebar Toggle**:
```javascript
function toggleSidebar() {
  // En mobile: toggle clase 'open' en sidebar + overlay
  // En desktop: toggle collapsed (solo iconos)
}
```

**Search**: filtro en tabla client-side (oculta filas que no coinciden).

**Form Handlers**:
- Submit AJAX para formularios con `fetch()`
- Manejo de CSRF: leer token de meta tag o campo oculto
- Mostrar loading spinner durante submit
- Manejar errores de validación

**Tabla dinámica (agregar/eliminar filas)**:
```javascript
function addTableRow(tableId, columns) { /* agrega fila con inputs */ }
function removeTableRow(button) { /* elimina fila */ }
```

**Inicialización**:
- Detectar tema del sistema al cargar
- Inicializar tooltips
- Cargar datos iniciales para gráficos (Chart.js)
- Configurar eventos de formularios

---

## 11. Reglas de Negocio Clave

### 11.1 Soft-delete universal
- NUNCA ejecutar `DELETE FROM` en tablas de negocio (solo en TrashItem.cleanup_all)
- Siempre set `is_active = False`, guardar razón
- Registrar quién y cuándo inactivó
- Guardar copia JSON en TrashItem
- Todas las consultas de listas deben filtrar `WHERE is_active = True` (o `is_active = 1`)

### 11.2 SCD Tipo 2 en ATAssignment
- `customer_name` NO tiene UNIQUE constraint
- Máximo un registro vigente por cliente (`valid_to IS NULL`)
- Al crear nueva asignación para cliente existente, cerrar la anterior (`valid_to = date_created` o fecha actual)
- `valid_from` y `valid_to` son solo fecha (sin hora)

### 11.3 JSON en SQLite
- **IMPORTANTE**: `json_extract` en SQLite retorna siempre texto
- Para filtrar por valores en arrays JSON con `in_()`, usar `.as_string()` en la columna
- Ejemplo: `db.query(Model).filter(Model.json_field.as_string().in_(values))`

### 11.4 Formulario de visita (17 tablas)
- Cada sección (materia_prima, parametros_proceso, etc.) es un array JSON
- Al guardar, serializar cada tabla a JSON string y almacenar en columna Text
- Al editar, deserializar cada JSON a array para renderizar las tablas
- Las filas del plan de acción se guardan en dos lugares:
  1. Como JSON dentro del campo `action_plan` de la visita
  2. Como registros individuales en `ActionPlanTracking` (para seguimiento)

### 11.5 Fotos
- Subir a `static/uploads/` con nombre único (timestamp + uuid)
- Guardar solo el nombre de archivo en el JSON `fotos`
- Servir desde `/static/uploads/{filename}`
- Permitir eliminar fotos individuales antes de guardar

### 11.6 Dashboard KPIs
- `visits_goal` = suma de `visit_goal` de todos los ATAssignment vigentes
- `visits_progress` = suma de `visits_completed` de todos los ATAssignment vigentes
- Mostrar barra de progreso: `progress / goal * 100`

---

## 12. Pruebas (tests/)

Usar pytest con test client de FastAPI. SQLite en memoria para cada test.

### test_auth.py
- Login exitoso
- Login fallido (credenciales incorrectas)
- Registro de usuario
- Logout

### test_customers.py
- CRUD cliente
- Soft-delete cliente
- Listar clientes activos

### test_products.py
- CRUD producto
- Productos por cliente

### test_machinery.py
- CRUD máquina

### test_visits.py
- Crear visita técnica
- Validación de campos requeridos
- Serialización JSON de tablas
- Soft-delete visita

### test_trash.py
- Elemento aparece en papelera tras soft-delete
- Restaurar elemento
- Vaciar papelera

Ejemplo de fixture:
```python
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = SessionLocal(bind=engine)
    yield session
    session.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
```

---

## 13. Esquemas Pydantic (app/schemas/)

Esquemas para validación de entrada/salida en rutas API JSON.

### visit.py
```python
class VisitCreate(BaseModel):
    fecha_visita: date
    customer_id: int
    technical_advisor_id: int | None = None
    designer_id: int | None = None
    commercial_advisor_id: int | None = None
    topic_id: int | None = None
    objective: str | None = None
    product_type: str | None = None
    codigo_muestra: str | None = None
    product_name: str | None = None
    forma: str | None = None
    plant: str | None = None
    maquina: str | None = None
    turno: str | None = None
    formado_type_id: int | None = None
    inferior_closure_id: int | None = None
    materia_prima: str | None = None       # JSON string
    parametros_proceso: str | None = None
    producto_terminado: str | None = None
    control_calidad: str | None = None
    observaciones: str | None = None
    plan_accion: str | None = None
    acciones: str | None = None
    action_plan: str | None = None
    fotos: str | None = None
```

### survey.py, customer.py, machine.py, meeting.py, at_assignment.py
- Esquemas Create, Update, Response similares

---

## 14. Migraciones (Alembic)

### alembic/env.py
- Leer `DATABASE_URL` de `config.settings.DATABASE_URL`
- Configurar `target_metadata = Base.metadata`
- Usar `render_as_batch=True` (requerido para SQLite)
- `compare_type=True`, `compare_server_default=True`

### Migraciones existentes (orden):
1. `initial_schema.py` — tablas base (users, customers, products, etc.)
2. `add_technical_visits_2_table.py`
3. `add_technical_surveys_2_table.py`
4. `add_trash_items_table.py`
5. `add_quality_topics_table.py`
6. `add_quality_at_topics_table.py`
7. `add_formado_and_closure_types.py`
8. `add_client_name_and_plant_name_tables.py`
9. `add_visit_type_and_distributor_plant_tables.py`
10. `add_distributor_plant_to_technical.py`
11. `add_autoincrement_to_technical_visits_2_.py`

---

## 15. Despliegue

### Variables de entorno (.env)
```
DATABASE_URL=postgresql://user:pass@host:5432/industrial_bi
SECRET_KEY=your-production-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure-password
```

### Dockerfile (crear si no existe)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Scripts package.json
```json
{
  "scripts": {
    "build:css": "tailwindcss -i ./app/static/css/input.css -o ./app/static/css/style.css",
    "watch:css": "tailwindcss -i ./app/static/css/input.css -o ./app/static/css/style.css --watch"
  }
}
```

---

## 16. Funcionalidades del Sistema (Resumen)

El sistema debe permitir:

1. **Autenticación**: login, registro, logout, sesión por cookie, JWT para API
2. **Gestión de Clientes**: alta, edición, baja lógica, listado con filtros
3. **Gestión de Productos**: asociados a cliente, alta, edición, baja lógica
4. **Gestión de Maquinaria**: asociada a cliente, con tipo de máquina
5. **Visitas Técnicas**: formulario completo con 17 tablas editables, fotos, firmas
6. **Relevamientos Técnicos**: dos versiones, con datos de calidad
7. **Relevamiento de Infraestructura**: personal, máquina, datos de planta
8. **Asignación AT**: SCD Tipo 2, equipo técnico por cliente
9. **Control AT**: monitoreo de asignaciones vs visitas realizadas
10. **KPIs de Calidad**: filtros múltiples, gráficos stacked por tema e impacto
11. **Dashboard**: KPIs globales, tendencias, últimas visitas
12. **Agenda**: calendario mensual con visitas como eventos
13. **Seguimiento**: plan de acción con cambios de estado
14. **Minutas**: reuniones con participantes, compromisos, próximos pasos
15. **Configuración**: gestión de 14 catálogos del sistema
16. **Papelera**: restauración de elementos eliminados
17. **Tema oscuro**: toggle manual, persistencia localStorage, respeta preferencia del sistema
18. **Diseño responsive**: sidebar colapsable en mobile, tablas con scroll horizontal
19. **Exportación**: (opcional) imprimir vistas de detalle

---

## 17. Instrucciones Finales para la IA

1. **NO uses librerías externas no listadas**. No React, No Vue, No Bootstrap, No jQuery.
2. **Todo el CSS debe estar en `style.css`** (además de las clases utility de Tailwind).
3. **El JS debe estar en `app.js`** (no dividir en múltiples archivos).
4. **Los templates Jinja2 deben heredar de `layout.html`** usando blocks.
5. **Los nombres de rutas, tablas, columnas y variables deben coincidir EXACTAMENTE** con lo especificado.
6. **Cada router debe tener su propio archivo** (no todo en `main.py`).
7. **Cada servicio debe encapsular lógica de negocio** (los routers solo llaman servicios).
8. **El formulario `nueva_visita2.html` es el más complejo**: dedica especial atención a las 17 tablas editables, la serialización JSON, la subida de fotos y las firmas.
9. **Los campos JSON en SQLite se almacenan como `Text`** (no como JSON nativo).
10. **No olvides el filtro CSRF** en cada ruta POST.
11. **La papelera (TrashItem) es crítica**: cada soft-delete debe crear un registro allí.
12. **Los catálogos (14 tablas) usan `BaseCatalogMixin`** para evitar repetir código.
13. **La aplicación debe funcionar con `uvicorn app.main:app --reload`** después de instalar dependencias y compilar CSS.
14. **Si algo no está especificado, usa el sentido común y mantenlo simple**.

---

## 18. Checklist de Archivos a Crear

- [ ] `requirements.txt`
- [ ] `package.json`
- [ ] `tailwind.config.js`
- [ ] `.gitignore` (incluir `*.db`, `__pycache__/`, `node_modules/`, `.env`)
- [ ] `app/__init__.py`
- [ ] `app/main.py`
- [ ] `app/config.py`
- [ ] `app/database.py`
- [ ] `app/models.py`
- [ ] `app/enums.py`
- [ ] `app/security.py`
- [ ] `app/logger.py`
- [ ] `app/utils.py`
- [ ] `app/routers/__init__.py`
- [ ] `app/routers/auth.py`
- [ ] `app/routers/customers.py`
- [ ] `app/routers/products.py`
- [ ] `app/routers/machinery.py`
- [ ] `app/routers/visits2.py`
- [ ] `app/routers/relevamiento.py`
- [ ] `app/routers/relevamiento2.py`
- [ ] `app/routers/infraestructura.py`
- [ ] `app/routers/kpis.py`
- [ ] `app/routers/dashboard.py`
- [ ] `app/routers/control_at.py`
- [ ] `app/routers/seguimiento.py`
- [ ] `app/routers/configuracion.py`
- [ ] `app/routers/agenda.py`
- [ ] `app/routers/minutas.py`
- [ ] `app/routers/trash.py`
- [ ] `app/services/__init__.py`
- [ ] `app/services/user_service.py`
- [ ] `app/services/customer_service.py`
- [ ] `app/services/product_service.py`
- [ ] `app/services/machine_service.py`
- [ ] `app/services/survey_service.py`
- [ ] `app/services/tracking_service.py`
- [ ] `app/services/kpi_service.py`
- [ ] `app/services/dashboard_service.py`
- [ ] `app/services/trash_service.py`
- [ ] `app/services/meeting_service.py`
- [ ] `app/services/agenda_service.py`
- [ ] `app/services/soft_delete.py`
- [ ] `app/services/pagination.py`
- [ ] `app/services/utils.py`
- [ ] `app/schemas/__init__.py`
- [ ] `app/schemas/visit.py`
- [ ] `app/schemas/survey.py`
- [ ] `app/schemas/customer.py`
- [ ] `app/schemas/machine.py`
- [ ] `app/schemas/meeting.py`
- [ ] `app/schemas/at_assignment.py`
- [ ] `app/templates/layout.html`
- [ ] `app/templates/login.html`
- [ ] `app/templates/register.html`
- [ ] `app/templates/clientes.html`
- [ ] `app/templates/nuevo_cliente.html`
- [ ] `app/templates/maquinaria.html`
- [ ] `app/templates/productos.html`
- [ ] `app/templates/visitas2_lista.html`
- [ ] `app/templates/nueva_visita2.html`
- [ ] `app/templates/relevamiento.html`
- [ ] `app/templates/relevamiento_ver.html`
- [ ] `app/templates/nuevo_relevamiento2.html`
- [ ] `app/templates/relevamiento2_lista.html`
- [ ] `app/templates/relevamiento_infraestructura_form.html`
- [ ] `app/templates/relevamiento_infraestructura_lista.html`
- [ ] `app/templates/dashboard.html`
- [ ] `app/templates/control_at.html`
- [ ] `app/templates/kpis_at.html`
- [ ] `app/templates/kpi_calidad.html`
- [ ] `app/templates/seguimiento_plan.html`
- [ ] `app/templates/agenda.html`
- [ ] `app/templates/configuracion.html`
- [ ] `app/templates/minutas_lista.html`
- [ ] `app/templates/nueva_minuta.html`
- [ ] `app/templates/trash.html`
- [ ] `app/static/css/input.css`
- [ ] `app/static/css/style.css`
- [ ] `app/static/css/fonts.css`
- [ ] `app/static/js/app.js`
- [ ] `app/static/js/chart.umd.min.js`
- [ ] `app/static/js/tabulator.min.js`
- [ ] `app/static/uploads/.gitkeep`
- [ ] `tests/test_auth.py`
- [ ] `tests/test_customers.py`
- [ ] `tests/test_products.py`
- [ ] `tests/test_machinery.py`
- [ ] `tests/test_visits.py`
- [ ] `tests/test_trash.py`
- [ ] `alembic.ini`
- [ ] `alembic/env.py`
- [ ] `alembic/versions/` (migraciones)
- [ ] `docs/funcionalidades.md`
- [ ] `docs/basededatos.md`
- [ ] `docs/prompt-para-ia.md`
- [ ] `Dockerfile` (opcional)
- [ ] `.env` (no commitear)

---

**FIN DEL PROMPT**

Entrega el código completo de la aplicación, archivo por archivo, con todo lo especificado arriba. La aplicación debe funcionar inmediatamente después de instalar dependencias, compilar CSS y ejecutar `uvicorn app.main:app --reload`.
