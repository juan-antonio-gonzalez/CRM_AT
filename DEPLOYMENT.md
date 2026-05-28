# Deployment Guide — CRM-AT (Industrial BI Dashboard)

Production deployment guide for the CRM-AT platform. Covers Docker-based deployment, database migration, security hardening, and CI/CD.

---

## Architecture

```
Internet ──▶ Nginx (HTTPS) ──▶ Gunicorn + Uvicorn Workers (port 8000) ──▶ PostgreSQL/SQLite
                                    │
                                    └── static/uploads/ (persistent volume)
```

---

## Quick Start (Docker Compose)

### Prerequisites

- Docker & Docker Compose
- Git

### Steps

```bash
git clone <your-repo-url> crm-at
cd crm-at

# Production startup (SQLite)
docker-compose up -d --build
# App available at http://localhost:8000
```

### With PostgreSQL

1. Uncomment the `db` service and `DATABASE_URL` in `docker-compose.yml`
2. Set strong credentials in `docker-compose.yml` or `.env`
3. Start:

```bash
docker-compose up -d --build
```

### Environment Variables (`.env`)

```env
DATABASE_URL=postgresql://user:password@db:5432/industrial_bi
SECRET_KEY=<generate-a-random-64-char-key>
DEBUG=false
CORS_ORIGINS=["https://yourdomain.com"]
LOG_LEVEL=INFO
```

---

## Dockerfile

Multi-stage build (`python:3.12-slim`):

| Stage | Base | Purpose |
|-------|------|---------|
| `builder` | `python:3.12-slim` | Compile dependencies (gcc, libpq-dev) |
| `runtime` | `python:3.12-slim` | Minimal runtime (only libpq5), non-root `app` user |

**CMD**: `gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4 --max-requests 1000`

---

## Nginx + HTTPS (Let's Encrypt)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo certbot --nginx -d yourdomain.com
```

---

## Security Hardening

### CSP

The app sets a strict CSP with per-request nonces. In production, ensure:

- All `<script>` tags include `nonce="{{ request.state.script_nonce }}"`
- No inline event handlers (`onclick`, `onchange`, etc.) — use `addEventListener` in nonced script blocks
- CDN origins in CSP match your dependencies

### CORS

Edit `main.py` or set `CORS_ORIGINS` env var:

```python
# config.py default: cors_origins: list[str] = ["*"]
# Override via .env or environment:
CORS_ORIGINS='["https://yourdomain.com"]'
```

### Secret Key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Set as SECRET_KEY in .env or environment
```

### CSRF

Enabled by default (`csrf_enabled: bool = True`). CSRF tokens are:

- Tied to the user's JWT session
- 1-hour expiry
- Auto-injected into forms via JavaScript
- Available in `<meta name="csrf-token">`

### Security Headers (auto-set)

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |

### Session

- JWT in HTTP-only cookie (`session`)
- `httponly`, `samesite=lax`, `max_age` = `session_expire_hours` (default 24h)
- `secure: true` recommended in production (set in `main.py`)

---

## Database Migrations

```bash
# Auto-generate migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### SQLite → PostgreSQL Migration

1. Set `DATABASE_URL` env var to PostgreSQL connection string
2. Run `alembic upgrade head`
3. Tables are created automatically by SQLAlchemy on first startup

---

## Backups

### SQLite

```bash
cp industrial_bi.db backups/industrial_bi_$(date +%Y-%m-%d).db
```

### PostgreSQL

```bash
docker exec -t crm-at_db_1 pg_dumpall -c -U admin_crm > dump_$(date +%Y-%m-%d).sql
```

### Uploaded Files

```bash
tar -czf uploads_$(date +%Y-%m-%d).tar.gz static/uploads/
```

---

## CI/CD (GitHub Actions)

Workflow: `.github/workflows/ci.yml`

| Job | Triggers | Steps |
|-----|----------|-------|
| `lint` | push (main/develop), PR (main) | `py_compile` syntax check, `ruff` linter |
| `test` | after lint | `pytest` (37 tests) |
| `docker` | after lint | Docker build (no push) |

---

## Monitoring

- Logs via `logger.py` — supports JSON structured logging (`LOG_JSON=true`)
- Log level configurable: `DEBUG`, `INFO`, `WARNING`, `ERROR` (`LOG_LEVEL` env var)
- All unhandled exceptions are caught globally, logged, and return 500 JSON

---

## Tailwind CSS (development only)

```bash
npm install
npm run tailwind-watch    # Watch mode for development
NODE_ENV=production npx tailwindcss -i static/css/input.css -o static/css/tailwind.css --minify
```

The compiled `static/css/tailwind.css` is gitignored — build it in CI or pre-build before deployment.

---

## Application Structure

```
├── main.py                  # FastAPI app, middleware, error handlers
├── config.py                # Pydantic settings (env vars)
├── database.py              # SQLAlchemy engine + session
├── models.py                # 18 ORM models
├── security.py              # JWT, bcrypt, CSRF
├── logger.py                # Structured logging
├── utils.py                 # Helper functions
├── routers/                 # Route modules (12 files)
│   ├── auth.py, dashboard.py, customers.py
│   ├── products.py, machinery.py, visits.py
│   ├── relevamiento.py, infraestructura.py
│   ├── kpis.py, seguimiento.py, configuracion.py
├── schemas/                 # Pydantic schemas (6 files)
├── templates/               # Jinja2 templates (32 files)
├── static/                  # CSS, JS, uploads
├── tests/                   # Pytest tests (6 files, 37 tests)
├── alembic/                 # DB migrations
└── .github/workflows/       # CI pipeline
```
