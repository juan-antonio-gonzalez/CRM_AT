# Guía de Uso — CRM-AT (Industrial BI Dashboard)

Plataforma integral para gestión comercial industrial: clientes, productos, maquinaria, relevamientos técnicos, visitas técnicas, planes de acción y KPIs.

---

## Índice
- [Stack Tecnológico](#stack-tecnológico)
- [Requisitos](#requisitos)
- [Instalación y Ejecución](#instalación-y-ejecución)
- [Módulos](#módulos)
- [Seguridad](#seguridad)
- [API](#api)
- [Mantenimiento](#mantenimiento)

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12+, FastAPI |
| Frontend | Jinja2 + Tailwind CSS 3 |
| Base de datos | SQLAlchemy ORM (SQLite local / PostgreSQL producción) |
| Autenticación | JWT + bcrypt + HTTP-only cookie |
| Seguridad | CSP con nonce, CSRF por sesión, headers de seguridad |
| UI/UX | Modo oscuro/claro, diseño responsive, iconos Material Symbols |
| Despliegue | Docker multi-stage, Gunicorn + Uvicorn workers |

---

## Requisitos

- Python 3.12 o superior
- Node.js 18+ (solo para compilar Tailwind CSS en desarrollo)
- Navegador moderno (Chrome, Edge, Firefox, Safari)

---

## Instalación y Ejecución

### 1. Clonar e instalar dependencias

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### 2. Compilar Tailwind CSS (desarrollo)

```bash
npm install
npm run tailwind-watch     # Recompila automáticamente al editar HTML
```

### 3. Iniciar servidor de desarrollo

```bash
python main.py
# o bien:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Acceder

Abrir `http://localhost:8000` en el navegador.

> El primer usuario debe crearse desde `/auth/register` (accesible sin autenticación la primera vez).

---

## Módulos

### 1. Dashboard (`/`)

Panel principal con métricas en tiempo real:
- Tarjetas de resumen: clientes, visitas, máquinas, relevamientos
- Gráfico de tendencia de visitas (6 meses)
- Gráfico de tipos de visita (circular)
- Gráfico de tópicos más discutidos (barras)
- Barra de búsqueda global (clientes, productos, máquinas)

### 2. Clientes (`/clientes`)

Gestión completa de clientes industriales:
- CRUD completo con nombre, planta, sector, dirección
- Equipo del cliente (nombre, rol, email) — filas dinámicas
- Asesor técnico y comercial asignados
- Estado: Prospecto / Activo / Inactivo
- Estado automático de relevamiento por máquina
- Reporte detallado por cliente con máquinas y visitas

### 3. Productos (`/productos`)

Catálogo de productos con trazabilidad:
- CRUD con número de ET (único), material, ruta de fabricación
- Dimensiones (largo, ancho, alto)
- Filtros por nombre, ET, material, estado
- API de búsqueda para autocompletado

### 4. Maquinaria (`/maquinaria`)

Inventario de activos industriales:
- Número de serie único, marca, modelo
- Asignación a cliente + planta + línea
- Tipo de máquina (desde tabla auxiliar)
- Estado operativo y estado de relevamiento
- Filtros por cliente, asesor técnico, búsqueda libre

### 5. Relevamientos Técnicos (`/relevamiento`)

Auditoría técnica de maquinaria en planta. El formulario captura:

**Sección 1 — Almacenamiento (Insumos y Producto Terminado):**
- Medidas de racks, temperatura/humedad, tiempo de almacenamiento
- Pallet sobre pallet, criticidad, observaciones
- *Campos separados para insumos y producto terminado*

**Sección 2 — Logística (Transporte y Distribución):**
- Tipo de vehículo, dimensiones de altura, ruta máxima
- Canal de venta, ubicación en estantería, frecuencia de reposición
- Criticidad y observaciones

**Sección 3 — Paletizado:**
- Tipo de paletizado, tipo de pallet, piezas por recepción
- Altura máxima de pallet, voladizo
- Uso de film stretch, protectores de esquina, interpallet
- Criticidad y observaciones

**Resumen y acciones:**
- Exportación a PDF del informe completo
- Vista de informe y vista detallada
- Estado: Borrador / Completado

### 6. Relevamientos de Infraestructura (`/relevamiento-infraestructura`)

Auditoría general de planta en 4 secciones (datos en JSON):
- Almacenamiento
- Packaging / Embalaje
- Paletizado
- Logística

Con reporte visual y exportable.

### 7. Visitas Técnicas (`/visitas`, `/agenda`)

Agenda y registro de visitas a clientes:
- Creación con fecha, participantes, tipo, objetivo
- Tópicos de visita (selección múltiple desde tabla auxiliar)
- Hallazgos de calidad y soporte
- Plan de acción integrado (tarea, responsable, fecha, estado)
- Subida de fotos con redimensionamiento automático (1024×768, JPEG Q85)
- Vista de calendario/agenda con códigos de color por estado
- Estados: Programada / Finalizada / Cancelada
- Los planes de acción se sincronizan automáticamente al tablero de seguimiento

### 8. Seguimiento Plan de Acción (`/seguimiento-plan`)

Tablero maestro de todas las tareas generadas en visitas:
- CRUD completo sin modificar la visita original
- Estados: Pendiente / En Proceso / Completado
- Filtros por cliente, estado, responsable
- Borrado lógico (is_active)
- KPIs de avance

### 9. KPIs / Asignación AT (`/kpis-at`)

Asignación de asesores técnicos y cuotas de visita:
- Asignación de AT por cliente
- Visitas standard y premium por período
- Indicador de atención requerida con observaciones
- Creación rápida inline desde la misma página

### 10. Configuración (`/configuracion`)

Tablas auxiliares editables sin tocar código:
- Asesores Técnicos
- Diseñadores
- Asesores Comerciales
- Sectores Industriales
- Tipos de Máquina
- Tópicos de Visita

### 11. Usuarios (`/auth/usuarios`, solo admin)

Gestión de usuarios del sistema:
- Crear usuarios (admin)
- Activar/desactivar cuentas
- Restablecer contraseñas
- Roles: admin / user

### 12. Perfil de Usuario (`/auth/perfil`)

- Actualizar datos personales (nombre, email, teléfono)
- Cambiar contraseña (requiere contraseña actual)

---

## Seguridad

### Content Security Policy (CSP)

```
default-src 'self'
script-src 'self' 'nonce-{token}' cdn.jsdelivr.net cdn.tailwindcss.com unpkg.com
style-src 'self' 'unsafe-inline' fonts.googleapis.com
font-src 'self' fonts.gstatic.com
img-src 'self' data:
connect-src 'self'
frame-ancestors 'none'
```

- Nonce único por petición — los scripts inline sin nonce son bloqueados
- Los event handlers inline (`onclick`, `onchange`, etc.) deben migrarse a `addEventListener` dentro de bloques `<script nonce="...">`

### Headers de Seguridad

| Header | Valor |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` |

### CSRF

- Token CSRF por sesión atado al JWT del usuario
- Expira en 1 hora
- Se inyecta automáticamente en todos los formularios POST vía JavaScript
- También disponible en `<meta name="csrf-token">`

### Autenticación

- JWT almacenado en cookie HTTP-only (`session`)
- Cookie: `httponly`, `samesite=lax`, `max_age=86400` (24h)
- Passwords hasheados con bcrypt

### Autorización

- Rutas de administración protegidas con `require_admin()`
- Usuarios no-admin reciben 403 en rutas de gestión de usuarios

---

## API

Endpoints JSON disponibles:

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/api/productos/search` | GET | Buscar productos por nombre/ET |
| `/api/productos/{et_number}` | GET | Obtener producto por número ET |
| `/api/productos/crear` | POST | Crear producto vía JSON |
| `/api/cliente-plantas/{name}` | GET | Plantas de un cliente |
| `/api/plantas-lineas/{name}/{plant}` | GET | Líneas de una planta |
| `/api/linea-maquinas/{name}/{plant}/{line}` | GET | Máquinas de una línea |
| `/api/planta-maquinas/{name}/{plant}` | GET | Máquinas de una planta |
| `/api/visitas-agenda` | GET | Visitas para calendario |
| `/api/visitas/{id}/status` | POST | Cambiar estado de visita |
| `/api/customers/quick-create` | POST | Crear asignación AT rápida |
| `/api/customers/{id}/update-kpis` | POST | Actualizar KPIs de asignación |
| `/api/customers/{id}/details` | GET | Detalles de cliente para KPIs |

---

## Mantenimiento

### Respaldo de datos (SQLite)

```bash
cp industrial_bi.db backups/industrial_bi_$(date +%Y-%m-%d).db
```

### Migraciones con Alembic

```bash
alembic revision --autogenerate -m "descripción"
alembic upgrade head
```

### Compilar Tailwind para producción

```bash
NODE_ENV=production npx tailwindcss -i static/css/input.css -o static/css/tailwind.css --minify
```

### CI/CD

GitHub Actions en `.github/workflows/ci.yml`:
- **lint**: Verifica sintaxis Python + ruff
- **test**: Ejecuta pytest (37 tests)
- **docker**: Build de imagen Docker sin push
- Dispara en push a `main`/`develop` y PR a `main`

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| Puerto 8000 ocupado | Cambiar con `--port 8001` o `kill $(lsof -ti:8000)` |
| Base de datos corrupta | Eliminar `industrial_bi.db` y reiniciar (se recrea sola) |
| Tailwind no se actualiza | Ejecutar `npm install` y `npm run tailwind-watch` |
| Error de migración Alembic | `alembic downgrade -1` y luego `alembic upgrade head` |
| Sesión expirada | Recargar la página → redirige al login |
| CSP bloquea script | Verificar que el `<script>` tenga atributo `nonce` |
