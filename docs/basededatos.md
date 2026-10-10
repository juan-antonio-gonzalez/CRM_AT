# Base de Datos — AplicaciónAT

Motor: **SQLite**  
Archivo: `industrial_bi.db`  
ORM: **SQLAlchemy** (declarative)

---

## Tablas del Esquema

### 1. `users` — Usuarios del sistema
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| username | VARCHAR UNIQUE | Login |
| email | VARCHAR UNIQUE | |
| hashed_password | VARCHAR | Bcrypt |
| full_name | VARCHAR | |
| phone | VARCHAR | |
| role | VARCHAR | `user` o `admin` |
| is_active | BOOLEAN | |
| avatar_url | VARCHAR | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### 2. `customers` — Clientes
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR | Nombre del cliente |
| plant | VARCHAR | Planta asignada |
| industry_sector | VARCHAR | Sector industrial |
| assigned_commercial | VARCHAR | Comercial asignado |
| technical_advisor | VARCHAR | Asesor técnico |
| designer | VARCHAR | Diseñador |
| address | VARCHAR | |
| city | VARCHAR | |
| status | VARCHAR | `Cliente` / `Prospecto` |
| relevamiento_status | VARCHAR | `Pendiente` / `En Proceso` / `Completado` |
| client_team | JSON | Equipo del cliente [{name, role, email}] |
| observations | TEXT | |
| standard_visits | INTEGER | Visitas estándar contratadas |
| premium_visits | INTEGER | Visitas premium contratadas |

### 3. `products` — Catálogo de productos
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| name | VARCHAR | |
| et_number | VARCHAR UNIQUE | Número ET |
| material | VARCHAR | |
| manufacturing_route | VARCHAR | Ruta de fabricación |
| dimensions_l / a / h | FLOAT | Largo, ancho, alto |
| status | VARCHAR | `Activo` / `Inactivo` |
| last_modified | VARCHAR | |

### 4. `machines` — Maquinaria/equipos
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| serial_number | VARCHAR UNIQUE | |
| model | VARCHAR | |
| brand | VARCHAR | |
| plant_assigned | VARCHAR | |
| machine_type | VARCHAR | |
| line | VARCHAR | Línea de producción |
| status | VARCHAR | `Operativo` / `Mantenimiento` / etc. |
| relevamiento_status | VARCHAR | |
| customer_id | INTEGER FK → customers.id | |

### 5. `meeting_minutes` — Minutas de Reunión
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| fecha | VARCHAR | Fecha de la reunión |
| status | VARCHAR | `Borrador` / `Finalizado` |
| form_data | JSON | Datos completos (fecha, hora, lugar, tipo, objetivo, participantes, agenda, desarrollo, acuerdos, tareas, firma) |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### 6. `technical_visits_2` — Visitas Técnicas (V2 — SKA-DES-FO-001 Rev.2)
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| fecha | VARCHAR | Fecha de la visita |
| status | VARCHAR | `En proceso` / `Finalizado` |
| form_data | JSON | Datos completos del formulario (participantes, objetivo, tablas 5-9, anexos con fotos como rutas de archivo, firma, observaciones, tipo_producto, planta) |
| is_active | BOOLEAN DEFAULT 1 | Soft delete |
| inactivation_reason | TEXT NULL | |
| inactivated_by_id | INTEGER NULL | |
| inactivated_at | DATETIME NULL | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### 7. `technical_surveys_2` — Relevamientos Técnicos V2
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| customer_id | INTEGER FK → customers.id (nullable) | |
| machine_id | INTEGER FK → machines.id (nullable) | |
| fecha | VARCHAR | |
| status | VARCHAR | `En proceso` / `Finalizado` |
| form_data | JSON | Datos completos del formulario (info cliente, maquinaria, estaciones 1-3 con fotos como rutas de archivo, equipo producción, resumen) |
| is_active | BOOLEAN DEFAULT 1 | Soft delete |
| inactivation_reason | TEXT NULL | |
| inactivated_by_id | INTEGER NULL | |
| inactivated_at | DATETIME NULL | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### 8. `technical_surveys` — Relevamientos Técnicos (V1, legacy)
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| machine_id | INTEGER FK → machines.id | |
| status | VARCHAR | `Borrador` / `Pendiente` / `Completado` |
| data | JSON | Todos los campos del formulario |
| created_at | DATETIME | |
| updated_at | DATETIME | |
| machine_name_backup | VARCHAR | Backup por si se borra la máquina |
| machine_serial_backup | VARCHAR | |

### 9. `infrastructure_surveys` — Relevamiento Infraestructura y Logística
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| customer_id | INTEGER FK → customers.id | |
| plant | VARCHAR | |
| date | DATETIME | |
| technical_advisor | VARCHAR | |
| status | VARCHAR | |
| storage_data | JSON | Datos de almacenamiento |
| packaging_data | JSON | Datos de empaque |
| palletizing_data | JSON | Datos de paletizado |
| logistics_data | JSON | Datos de logística |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### 10. `action_plan_tracking` — Seguimiento de Plan de Acción
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| customer_name | VARCHAR | |
| plant | VARCHAR | |
| visit_date | DATETIME | |
| task | TEXT | |
| responsible | VARCHAR | |
| due_date | VARCHAR | |
| status | VARCHAR | `Pendiente` / `En curso` / `Finalizado` / `Cancelado` |
| et_number | VARCHAR | Número ET del producto relacionado |
| observations | TEXT | |
| source_visit_id | INTEGER | FK a technical_visits_2.id |
| is_active | BOOLEAN | |
| created_at / updated_at | DATETIME | |

### 11. `at_assignments` — Asignaciones de Asistencia Técnica (SCD Tipo 2)
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| customer_name | VARCHAR | |
| technical_advisor | VARCHAR | |
| standard_visits | INTEGER | |
| premium_visits | INTEGER | |
| attention_required | BOOLEAN | |
| attention_observations | TEXT | |
| status | VARCHAR | `Activo` / `Inactivo` / `Fuera de Cronograma` |
| valid_from | DATETIME | Inicio de vigencia |
| valid_to | DATETIME NULL | Fin de vigencia; `NULL` = vigente |

Notas:
- `customer_name` **no es UNIQUE** (se permiten múltiples filas vigentes con distinto `valid_from` para el mismo cliente — SCD Tipo 2)
- La unicidad lógica se maneja por aplicación: 1 fila vigente (`valid_to IS NULL`) por cliente a la vez

Comportamiento:
- Al editar una asignación existente, la fila vigente se cierra (`valid_to = now`) y se crea una nueva fila con `valid_from = now`, formando un historial de cambios.
- La tabla `/control-at` muestra solo filas vigentes (`valid_to IS NULL`).
- Al filtrar por AT en los KPIs se suman todas las versiones (históricas + vigentes).
- Las tablas de agenda y dashboard también consultan solo vigentes.

### 12. `trash_items` — Papelera (eliminación suave)
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | |
| entity_type | VARCHAR | Tipo de entidad eliminada |
| entity_id | INTEGER | |
| entity_name | VARCHAR | |
| data | JSON | Datos completos antes de eliminar |
| deleted_by | INTEGER | |
| deleted_by_name | VARCHAR | |
| deleted_at | DATETIME | |
| restored_at | DATETIME | |
| restored_by | INTEGER | |

### 11–21. Tablas auxiliares (catálogos)
Todas con estructura `{id INTEGER PK, name VARCHAR UNIQUE}`.
Los valores se almacenan automáticamente en **MAYÚSCULAS** mediante `@validates('name')` en el modelo:

| Tabla | Propósito |
|---|---|
| `technical_advisors` | Asesores técnicos |
| `designers` | Diseñadores |
| `commercial_advisors` | Asesores comerciales |
| `industrial_sectors` | Sectores industriales |
| `machine_types` | Tipos de máquina |
| `visit_topics` | Tópicos de visita |
| `formado_types` | Tipos de formado |
| `inferior_closure_types` | Tipos de cierre inferior |
| `client_names` | Nombres de cliente (catálogo) |
| `plant_names` | Nombres de planta (catálogo) |
| `distributor_plants` | Plantas distribuidoras |
| `visit_types` | Tipos de visita |
| `quality_topics` | Temas de Calidad (tabla 6) |
| `quality_at_topics` | Calidad AT (tabla 7) |
| `formado_types` | Tipos de formado (estación 2) |
| `inferior_closure_types` | Tipos de cierre inferior (estación 2) |

### 22. `alembic_version`
Tabla interna de Alembic que registra la migración aplicada.

---

## Relaciones Clave

```
customers ──1:N──> machines
customers ──1:N──> infrastructure_surveys
customers ──1:N──> technical_surveys_2
machines   ──1:N──> technical_surveys (V1)
machines   ──1:N──> technical_surveys_2 (V2, nullable)
```

## Soft Delete (is_active)

Todas las tablas principales y catálogos incluyen 4 columnas de soft delete:

| Columna | Tipo | Descripción |
|---|---|---|
| `is_active` | BOOLEAN DEFAULT 1 | `True` = activo, `False` = desactivado |
| `inactivation_reason` | TEXT NULL | Motivo obligatorio al desactivar |
| `inactivated_by_id` | INTEGER NULL | ID del usuario que desactivó |
| `inactivated_at` | DATETIME NULL | Momento de la desactivación |

- "Eliminar" un registro siempre es `UPDATE is_active = False`
- Solo el admin puede reactivar
- Los registros inactivos se muestran como solo lectura en la UI

---

## Notas sobre acceso a campos JSON en SQLite

SQLite almacena JSON como texto plano. La función `json_extract()` siempre retorna texto, incluso para valores numéricos.

### Reglas:
- **NO usar** `.as_integer()` para filtrar valores JSON en SQLite — SQLAlchemy no castea realmente el tipo, y los filtros `in_()` fallan porque comparan int contra string.
- **Usar** `.as_string()` y comparar con strings:
  ```python
  # ✅ Correcto
  models.TechnicalVisit2.form_data["cliente_id"].as_string() == str(cliente)
  models.TechnicalVisit2.form_data["cliente_id"].as_string().in_(str_ids)
  
  # ❌ Incorrecto (falla en SQLite)
  models.TechnicalVisit2.form_data["cliente_id"].as_integer() == cliente
  ```
- `.astext` también funciona (genera `CAST(... AS TEXT)`), pero `.as_string()` es más explícito.

### Tablas con `form_data` JSON:
- `technical_visits_2` — datos completos del formulario V2
- `technical_surveys_2` — datos del relevamiento V2
- `meeting_minutes` — datos de la minuta

---

## Notas sobre almacenamiento de imágenes

- **Visitas Técnicas V2:** las fotos de anexos se almacenan como archivos JPEG en `static/uploads/` (redimensionadas a máx. 1200px ancho, calidad 80%), no como base64 en la base de datos.
- **Relevamientos Técnicos V2:** las fotos de estaciones se almacenan como archivos JPEG en `static/uploads/relevamiento2/` (redimensionadas a máx. 1200px ancho, calidad 80%), no como base64.
- Al eliminar un registro, los archivos de fotos asociados se borran del disco.
- Requiere Pillow instalado (`pip install Pillow`).

---
