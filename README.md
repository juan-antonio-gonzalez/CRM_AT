# CRM-AT

Aplicación web de gestión de visitas técnicas, seguimiento de planes de acción y
relevamientos de infraestructura.

**Stack:** FastAPI · SQLAlchemy · Alembic · Jinja2 · Tailwind CSS
**Base de datos:** PostgreSQL (único motor, tanto en desarrollo como en producción).
100 % local: sin CDN, sin Google Fonts, sin dependencias de red en el navegador.

- **Repositorio:** https://github.com/juan-antonio-gonzalez/CRM_AT
- **Rama principal:** `main`
- **Despliegue en el VPS:** ver [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Puesta en marcha en desarrollo

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

cp deploy/env.example .env         # y editá SECRET_KEY y ADMIN_PASSWORD

# Crear el esquema y sembrar catálogos + administrador inicial
alembic upgrade head
python main.py seed

uvicorn main:app --reload
```

La aplicación queda en http://127.0.0.1:8000. El usuario inicial es el de
`ADMIN_USERNAME` (por defecto `admin`) con la contraseña de `ADMIN_PASSWORD`.

> El esquema se crea **con Alembic**, nunca con `create_all`. Eso es deliberado:
> durante mucho tiempo la aplicación llamaba `create_all` al arrancar, lo que
> enmascaraba que las migraciones no reproducían el esquema real y hacía que un
> despliegue limpio fallara con `no such column`. Hay tests que verifican que
> ambos coinciden (`tests/test_schema.py`).

### Comandos útiles

```bash
python main.py check-schema      # revisión de esquema aplicada
python main.py seed              # catálogos + administrador inicial (idempotente)
python main.py seed --demo       # además, datos de demostración
python main.py create-admin      # solo el administrador inicial

alembic upgrade head             # aplicar migraciones
alembic revision --autogenerate -m "descripcion"
alembic downgrade -1

pytest -q                        # tests (requieren PostgreSQL, ver abajo)
```

### Base de datos para desarrollo y pruebas

PostgreSQL es el único motor soportado. El proyecto antes soportaba SQLite en
desarrollo, y eso resultó contraproducente: el motor permisivo aceptaba en
silencio esquemas y datos que PostgreSQL rechaza, así que los errores aparecían
recién en el servidor. Con un solo motor, lo que probás es lo que se despliega.

Necesitás un PostgreSQL accesible:

```bash
# Una sola vez: crear el rol y las bases
sudo -u postgres psql -c "CREATE ROLE crm_at LOGIN PASSWORD 'crm_at';"
sudo -u postgres psql -c "CREATE DATABASE crm_at OWNER crm_at;"
sudo -u postgres psql -c "CREATE DATABASE crm_at_test OWNER crm_at;"

# Aplicar el esquema
export DATABASE_URL="postgresql://crm_at:crm_at@127.0.0.1:5432/crm_at"
alembic upgrade head
python main.py seed
```

Para correr las pruebas:

```bash
DATABASE_URL="postgresql://crm_at:crm_at@127.0.0.1:5432/crm_at" pytest -q
```

Las pruebas usan una base cuyo nombre termina en `_test` y la reconstruyen
corriendo las migraciones. Si la URL no contiene `_test`, la configuración se
niega a correr, para no destruir datos reales.

---

## Estructura

```
main.py                 arranque, middleware, manejadores de error, CLI de sembrado
config.py               settings (pydantic-settings) y normalización de DATABASE_URL
database.py             engine de PostgreSQL, get_db
models.py               modelos SQLAlchemy
enums.py                vocabularios de estado + normalización
templating.py           entorno Jinja2 compartido y filtros
routers/                endpoints (18 módulos)
services/               lógica de negocio y consultas
alembic/versions/       migraciones
templates/              plantillas Jinja2
static/                 CSS/JS/fuentes servidos localmente
deploy/                 instalador, unidad systemd, vhost Nginx, backups
tests/                  pruebas
```

---

## Notas de operación

- **`/health`** devuelve el estado de la base y la revisión de esquema aplicada.
  Está exento de autenticación y es lo que debe usar el healthcheck del proxy.
- **Papelera**: el borrado guarda un snapshot JSON y luego borra la fila.
  "Restaurar" reinserta el snapshot de verdad; si la clave natural ya está en uso,
  informa el motivo en lugar de simular éxito.
- **Sesiones**: `COOKIE_SECURE` debe reflejar si el sitio se sirve por HTTPS. Si
  está en `true` sobre HTTP, el navegador no envía la cookie y el login no funciona.
- **Logs**: `LOG_JSON=true` emite logs en JSON, útil para agregadores.

## Estado de los arreglos

Las correcciones aplicadas sobre la auditoría inicial (esquema y migraciones,
arranque sin bloqueo, plantillas rotas, build de CSS, integridad de datos,
accesibilidad y consolidación de UI) están descritas con su justificación en los
comentarios del código y en los mensajes de commit.
