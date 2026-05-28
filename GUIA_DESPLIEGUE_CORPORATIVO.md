# Guía de Despliegue Corporativo — CRM-AT (Industrial BI Dashboard)

Guía completa para desplegar CRM-AT en un entorno empresarial de producción con alta disponibilidad, seguridad HTTPS, y facilidad de mantenimiento.

---

## Índice

- [Arquitectura](#1-arquitectura-recomendada)
- [Preparación del Servidor](#2-preparación-del-servidor)
- [Despliegue con Docker](#3-despliegue-con-docker)
- [Base de Datos](#4-base-de-datos)
- [Proxy Inverso y HTTPS](#5-nginx--https)
- [Seguridad](#6-seguridad)
- [Mantenimiento](#7-mantenimiento)
- [CI/CD](#8-cicd)
- [Troubleshooting](#9-troubleshooting)

---

## 1. Arquitectura Recomendada

```
                     ┌─────────────┐
                     │   Internet   │
                     └──────┬──────┘
                            │ HTTPS :443
                     ┌──────▼──────┐
                     │    Nginx     │ (Proxy inverso + SSL)
                     │  (Certbot)   │
                     └──────┬──────┘
                            │ HTTP :8000
                     ┌──────▼──────┐
                     │   Docker    │
                     │  CRM-AT     │ ← Gunicorn + 4 Uvicorn workers
                     │             │
                     │  static/    │ ← Volumen persistente para uploads
                     │  uploads/   │
                     └──────┬──────┘
                            │
               ┌────────────┴────────────┐
               │                         │
        ┌──────▼──────┐          ┌──────▼──────┐
        │  PostgreSQL  │          │   SQLite    │
        │(recomendado) │          │  (default)  │
        └──────────────┘          └─────────────┘
```

### Componentes

| Componente | Tecnología | Versión |
|-----------|-----------|---------|
| Servidor | Ubuntu Server / Debian | 22.04 LTS+ |
| Proxy inverso | Nginx | latest |
| SSL/TLS | Let's Encrypt (Certbot) | latest |
| Contenedor | Docker + Docker Compose | latest |
| App Server | Gunicorn + Uvicorn | workers=4 |
| Base de datos | PostgreSQL 15 (prod) / SQLite (dev) | |

---

## 2. Preparación del Servidor

### 2.1 Actualizar sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Instalar dependencias base

```bash
sudo apt install -y git curl nginx certbot python3-certbot-nginx
```

### 2.3 Instalar Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Cerrar sesión y volver a entrar para aplicar el grupo docker
```

### 2.4 Instalar Docker Compose

```bash
sudo apt install -y docker-compose-plugin
# o descargar binary:
# sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
# sudo chmod +x /usr/local/bin/docker-compose
```

---

## 3. Despliegue con Docker

### 3.1 Clonar el repositorio

```bash
sudo mkdir -p /opt
cd /opt
sudo git clone <url-del-repositorio> crm-at
sudo chown -R $USER:$USER crm-at
cd crm-at
```

### 3.2 Configurar variables de entorno

Crear archivo `.env` en la raíz:

```bash
nano .env
```

```env
# --- Seguridad ---
SECRET_KEY=<generar con: python3 -c "import secrets; print(secrets.token_hex(32))">

# --- Base de Datos (SQLite por defecto) ---
# Para PostgreSQL, descomentar:
# DATABASE_URL=postgresql://crm_user:password_seguro@localhost:5432/crm_db

# --- Aplicación ---
DEBUG=false
LOG_LEVEL=INFO
LOG_JSON=false

# --- CORS (producción) ---
# CORS_ORIGINS='["https://crm.tuempresa.com"]'
```

> **IMPORTANTE**: `SECRET_KEY` debe ser única por despliegue. Sin ella, los tokens JWT son predecibles.

### 3.3 Desplegar contenedores

```bash
docker compose up -d --build
```

Verificar:

```bash
docker compose ps
docker compose logs -f
```

La aplicación responde en `http://<IP_DEL_SERVIDOR>:8000`.

---

## 4. Base de Datos

### 4.1 SQLite (por defecto)

- Archivo: `industrial_bi.db` en la raíz del proyecto
- Montado como volumen en `docker-compose.yml`
- **No apto para producción con alta concurrencia**

### 4.2 Migrar a PostgreSQL

1. Descomentar el servicio `db` y la variable `DATABASE_URL` en `docker-compose.yml`
2. Ajustar credenciales:

```yaml
services:
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: crm_user
      POSTGRES_PASSWORD: <password_seguro>
      POSTGRES_DB: crm_db
    restart: always

volumes:
  postgres_data:
```

3. Reconstruir y levantar:

```bash
docker compose up -d --build
```

4. Las tablas se crean automáticamente al arrancar la aplicación por primera vez.

### 4.3 Migraciones con Alembic

```bash
# Ejecutar dentro del contenedor web:
docker compose exec web alembic upgrade head

# Auto-generar migración tras cambios en models.py:
docker compose exec web alembic revision --autogenerate -m "descripcion"
```

---

## 5. Nginx + HTTPS

### 5.1 Configurar Nginx como proxy inverso

```bash
sudo nano /etc/nginx/sites-available/crm-at
```

```nginx
server {
    listen 80;
    server_name crm.tuempresa.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /opt/crm-at/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 5.2 Habilitar sitio y verificar

```bash
sudo ln -s /etc/nginx/sites-available/crm-at /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5.3 Certificado SSL con Let's Encrypt

```bash
sudo certbot --nginx -d crm.tuempresa.com
```

Seleccionar **Redirect** para redirigir todo el tráfico HTTP a HTTPS.

Certbot renueva automáticamente los certificados. Verificar renovación:

```bash
sudo certbot renew --dry-run
```

---

## 6. Seguridad

### 6.1 Headers de Seguridad

La aplicación envía automáticamente:

| Header | Valor | Propósito |
|--------|-------|-----------|
| `X-Content-Type-Options` | `nosniff` | Evita MIME sniffing |
| `X-Frame-Options` | `DENY` | Previene clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Protección XSS en navegadores antiguos |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control de referer |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restringe APIs del navegador |

### 6.2 Content Security Policy (CSP)

Policy actual:

```
default-src 'self';
script-src 'self' 'nonce-{token}' cdn.jsdelivr.net cdn.tailwindcss.com unpkg.com;
style-src 'self' 'unsafe-inline' fonts.googleapis.com;
font-src 'self' fonts.gstatic.com;
img-src 'self' data:;
connect-src 'self';
frame-ancestors 'none';
```

- Nonce único por request — cada script inline debe llevar `nonce="{{ request.state.script_nonce }}"`
- **No usar** event handlers inline (`onclick`, `onchange`, etc.) — usar `addEventListener` dentro de bloques `<script nonce="...">`

### 6.3 CORS

En producción, restringir orígenes en `.env`:

```env
CORS_ORIGINS='["https://crm.tuempresa.com"]'
```

### 6.4 Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 6.5 Hardening adicional

- Ejecutar contenedor con usuario no-root (`USER app` en Dockerfile)
- No exponer el puerto 8000 directamente a Internet
- Usar passwords fuertes para PostgreSQL
- Rotar `SECRET_KEY` periódicamente
- Monitorear logs: `docker compose logs -f --tail=100`

---

## 7. Mantenimiento

### 7.1 Actualizar aplicación

```bash
cd /opt/crm-at
git pull origin main
docker compose up -d --build
```

### 7.2 Respaldos

**Base de datos SQLite:**

```bash
# Script para cron (diario)
docker compose exec web cp industrial_bi.db /app/static/uploads/backup_$(date +%Y-%m-%d).db
```

**Base de datos PostgreSQL:**

```bash
docker compose exec db pg_dumpall -c -U crm_user > backup_$(date +%Y-%m-%d).sql
```

**Archivos subidos (fotos de visitas):**

```bash
tar -czf uploads_$(date +%Y-%m-%d).tar.gz /opt/crm-at/static/uploads/
```

### 7.3 Cron job recomendado

```bash
sudo crontab -e
```

```cron
# Backup diario a las 3 AM
0 3 * * * cd /opt/crm-at && docker compose exec -T web cp industrial_bi.db static/uploads/backup_$(date +\%Y-\%m-\%d).db
# Limpiar backups mayores a 30 días
0 4 * * * find /opt/crm-at/static/uploads -name "backup_*.db" -mtime +30 -delete
```

### 7.4 Logs y monitoreo

```bash
# Logs de la aplicación
docker compose logs -f web

# Logs de Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# JSON logging (habilitar con LOG_JSON=true en .env)
```

---

## 8. CI/CD

Pipeline GitHub Actions (`.github/workflows/ci.yml`):

| Job | Descripción | Triggers |
|-----|------------|----------|
| `lint` | Verifica sintaxis Python + ruff | push a main/develop, PR a main |
| `test` | Ejecuta 37 tests con pytest | después de lint |
| `docker` | Build de imagen Docker (sin push) | después de lint |

Ejemplo de deploy automático (agregar al workflow):

```yaml
deploy:
  needs: test
  runs-on: ubuntu-latest
  if: github.ref == 'refs/heads/main'
  steps:
    - uses: appleboy/ssh-action@v1
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USER }}
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /opt/crm-at
          git pull origin main
          docker compose up -d --build
```

---

## 9. Troubleshooting

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| Contenedor no arranca | Puerto 8000 ocupado | `lsof -i:8000` y liberar |
| Error "No module named uvicorn" | Dependencias no instaladas | Verificar `pip install -r requirements.txt` |
| 502 Bad Gateway | Nginx no alcanza la app | Verificar `docker compose ps` |
| Certificado SSL expirado | No se renovó automáticamente | `sudo certbot renew` |
| CSP bloquea funcionalidad | Inline handler sin nonce | Migrar a `addEventListener` |
| CSRF token inválido | Sesión expirada o cookie perdida | Recargar y re-autenticar |
| Error de conexión PostgreSQL | Credenciales incorrectas | Verificar `.env` y `docker-compose.yml` |
| Fotos no se ven | Volumen no montado | Verificar `static/uploads` en `docker-compose.yml` |

---

## Referencias

- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Gunicorn + Uvicorn](https://www.uvicorn.org/deployment/#running-with-gunicorn)
- [Nginx + Let's Encrypt](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [Docker Compose](https://docs.docker.com/compose/)
