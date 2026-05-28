# APP_AT

Aplicación de gestión de visitas técnicas, seguimiento de planes de acción y relevamientos.

## Deploy en Render.com

### 1. Crear PostgreSQL gratis
- Ve a [Neon.tech](https://neon.tech) y regístrate (0.5 GB gratis)
- Crea un proyecto y copia la **connection string** (parecida a `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb`)

### 2. Conectar repositorio
- Ve a [render.com](https://render.com) → New + → **Web Service**
- Conecta tu cuenta de GitHub y selecciona `APP_AT`
- Render detectará el `Dockerfile` automáticamente

### 3. Configurar el servicio
| Campo | Valor |
|-------|-------|
| Name | `app-at` |
| Region | la más cercana |
| Branch | `main` |
| Plan | **Free** |
| Health Check Path | `/` |

### 4. Variables de entorno
Agrega estas variables en Render:

| Variable | Valor |
|----------|-------|
| `DATABASE_URL` | La connection string de Neon (reemplazar `?sslmode=require` al final) |
| `SECRET_KEY` | Una clave secreta (ej. `abc123def456...`) |
| `DEBUG` | `false` |
| `CSRF_ENABLED` | `true` |

### 5. Crear el servicio
- Click en **Create Web Service**
- Render construirá y desplegará automáticamente
- Obtendrás una URL como `https://app-at.onrender.com`

### 6. Correr migraciones (primer deploy)
Una vez desplegado, abre la shell de Render desde el dashboard y ejecuta:
```bash
alembic upgrade head
```

### 7. Actualizar después de cambios
Solo haz push a GitHub y Render se redeploya automáticamente.

---

> ⚠️ **Importante:** En local sigues usando SQLite. En producción (Render) usas PostgreSQL. La app funciona con ambas gracias a la variable `DATABASE_URL`.

- **Repositorio:** https://github.com/juan-antonio-gonzalez/APP_AT
- **Rama principal:** `main`

### Comandos básicos

```bash
# Clonar
git clone https://github.com/juan-antonio-gonzalez/APP_AT.git

# Ver estado
git status

# Agregar cambios
git add .
git commit -m "mensaje"

# Subir
git push

# Traer cambios del remoto
git pull