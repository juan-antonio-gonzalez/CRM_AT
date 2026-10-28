# Funcionalidades — AplicaciónAT

Stack: **FastAPI + SQLAlchemy + SQLite + Jinja2 + Tailwind CSS**  
100% local, sin dependencias externas (sin CDN, sin Google Fonts).

---

## 1. Autenticación y Usuarios (`/auth/*`)

| Ruta | Descripción |
|---|---|
| `GET /auth/login` | Login page |
| `POST /auth/login` | Autentica con username/email + password, setea cookie JWT |
| `GET /auth/register` | Formulario de registro (solo admin) |
| `POST /auth/register` | Crea nuevo usuario (admin) |
| `GET /auth/logout` | Cierra sesión |
| `GET /auth/usuarios` | Lista de usuarios (admin) |
| `POST /auth/usuarios/{id}/toggle` | Activar/desactivar usuario (admin) |
| `POST /auth/usuarios/{id}/reset-password` | Resetear contraseña (admin) |
| `GET /auth/usuarios/{id}/editar` | Editar la cuenta y **elegir qué pantallas ve** (admin) |
| `POST /auth/usuarios/{id}/editar` | Guarda esos cambios (admin) |
| `GET /auth/perfil` | Perfil del usuario actual |
| `POST /auth/perfil` | Actualizar nombre, email, teléfono |
| `POST /auth/perfil/password` | Cambiar contraseña |

### Roles y permisos por pantalla

Hay dos roles: `admin` (ve todo y administra las cuentas) y `user`.

Además, **cada cuenta tiene su propia lista de pantallas que puede ver**, y se elige
con casillas desde `Editar usuario` → **Qué ve esta cuenta**. Un usuario común ve
exactamente las pantallas marcadas: las que no tiene **no aparecen en su menú y
tampoco se pueden abrir escribiendo la dirección** (dan error 403).

Tres estados posibles de esa lista:

- **Sin configurar** — ve todas las pantallas menos las de administración, y además
  las que se agreguen más adelante. Es el estado de las cuentas que ya existían.
- **Con pantallas marcadas** — ve exactamente ésas.
- **Ve todas las pantallas** (la casilla de arriba) — lo mismo que «sin configurar».

Una cuenta con rol **Administrador** ve todo siempre, sin importar la lista: no se le
puede restringir. Las pantallas **Usuarios** y **Papelera** son sólo para
administradores y no se pueden asignar a un usuario común.

La lista se puede configurar por pantalla, y cada grupo del menú (Análisis,
Operaciones, Gestión) tiene un botón **Marcar todo** para darlo entero de una vez.

Cambiar los permisos tiene efecto inmediato, y **desactivar una cuenta la echa en el
acto**: no hay que esperar a que venza la sesión.

---

## 2. Dashboard (`/`)

### KPIs - AT (`/`)
- Filtros: AT, Cliente, Año, Mes
- Secciones: Clientes (Total, Activos, Inactivos), Visitas (Total, Borrador, Finalizado, Objetivo/Avance con barra de progreso, Tendencia mensual, Motivos, Por AT), Máquinas (Total, Avance, Por Tipo/Estado/Relevamiento), Minutas (Total, Borrador, Finalizado, Por Tipo de Reunión)
- Gráfico de visitas por mes (tendencia).
- Gráfico de visitas por objetivo (extraído del `form_data` de V2).

### KPIs Calidad AT (`/kpi-calidad`)
- **Punto 7 — Asistencia Técnica:** gráfico de barras horizontales con colores individuales por barra (paleta de 13 colores)
- Contador de registros totales (no solo top 8)
- **Filtros:** Año, Mes, AT, Cliente, Tema, Tipo Producto, Planta — con recarga de página vía GET y headers `Cache-Control: no-cache`
- Link "Limpiar" para resetear todos los filtros

---

## 3. Clientes (`/clientes`)

| Acción | Ruta |
|---|---|
| Listar / buscar | `GET /clientes` |
| Nuevo cliente | `GET /POST /nuevo-cliente` |
| Editar cliente | `GET /editar-cliente/{id}` (partial) / `POST /editar-cliente/{id}` |
| Reporte cliente | `GET /cliente-reporte/{id}` (Informe Estratégico de Cuenta, para imprimir) |
| Eliminar cliente | `POST /eliminar-cliente/{id}` (va a papelera) |
| Exportar Excel | `GET /clientes/exportar-excel` |

### Un cliente se asigna a un EQUIPO, no a tres personas sueltas

El formulario **no** tiene tres desplegables (comercial, diseñador, AT): tiene un
solo selector, **Equipo asignado**. Al elegir un equipo, sus tres integrantes se
muestran debajo en modo lectura, para ver a quién se le asigna la cuenta antes de
guardar. Los tres nombres se copian a la ficha del cliente.

### Imprimir el informe del cliente

`GET /cliente-reporte/{id}` es el **Informe Estratégico de Cuenta**: la ficha del
cliente con sus contactos, su parque de maquinaria, el historial de visitas y las
observaciones, lista para imprimir o guardar en PDF con el botón **Imprimir
Reporte**.

El informe se reparte en **hojas A4**: si el contenido no entra en una, se agregan
las que hagan falta y cada hoja lleva su pie con el número —«Página 2 de 6»—. Las
tablas que cruzan de hoja repiten su encabezado, y las tarjetas de máquina no se
parten al medio. Con un cliente chico sale una sola hoja.

### Sí: cada planta puede tener un equipo distinto

**Sí, un cliente puede tener un equipo distinto en cada planta.** No hay un equipo
único del cliente: el equipo se asigna **por planta**.

Un cliente con tres plantas (tres fichas, una por planta) puede tener tres equipos
diferentes, uno en cada una, con comerciales, diseñadores y AT distintos. «El equipo
del cliente» siempre quiere decir «el equipo de esa planta».

Al editar la ficha de una planta, hay una casilla **«Aplicar este equipo también a
las otras N plantas»**: sin marcarla, sólo cambia esa planta.

Cambiar de equipo en la ficha **sí** reescribe los tres nombres del cliente. Lo que
no los reescribe es editar el equipo: ver la sección de Equipos.

El formulario incluye:
- Datos básicos (nombre, planta, sector, ciudad)
- **Equipo asignado** (un solo selector; los tres integrantes se ven debajo)
- **Equipo del cliente:** tabla dinámica con columnas Nombre Completo (select + quick-add desde catálogo `ContactName`), Reporta a (select del mismo equipo), Sector/Departamento (select + quick-add desde catálogo `MemberSector`), Cargo/Función (mayúsculas forzadas), Teléfono
- Observaciones
- Visitas estándar y premium contratadas

---

## 3b. Organigrama de Clientes (`/organigrama`)

| Acción | Ruta |
|---|---|
| Ver organigrama | `GET /organigrama` |
| API datos equipo | `GET /api/cliente-team/{customer_id}` |

- Selector de cliente en la parte superior
- Carga vía API los miembros del `client_team` (con `reports_to` y `sector`)
- Renderiza árbol jerárquico agrupado por Sector/Departamento
- Miembros sin `reports_to` son raíces; los que reportan a alguien se anidan debajo
- Miembros sin sector se agrupan en "SIN SECTOR"

---

## 3c. Equipos (`/equipos`)

Un **equipo** es un comercial, un diseñador y un AT, con un nombre. Es lo que se le
asigna a un cliente en lugar de elegir las tres personas por separado.

| Acción | Ruta |
|---|---|
| Listar / buscar equipos | `GET /equipos` |
| Nuevo equipo (modal) | `POST /equipos/nuevo` |
| Editar equipo | `GET /POST /equipos/{id}/editar` |
| Desactivar equipo (con motivo) | `POST /equipos/{id}/desactivar` |
| Reactivar equipo | `POST /equipos/{id}/reactivar` |
| Actualizar las asignaciones | `POST /equipos/{id}/actualizar-asignaciones` |

### Reglas

- **El equipo se asigna por planta.** Un cliente con tres plantas puede tener tres
  equipos distintos, uno en cada planta: no hay un equipo único del cliente.
- **Los tres integrantes son obligatorios.** No hay equipo incompleto.
- **Un equipo no se elimina: se desactiva**, y pide un motivo. Los clientes que lo
  tuvieron guardan su referencia, así que borrarlo no tendría sentido.
- **La misma persona puede estar en varios equipos**, y puede tener dos roles en el
  mismo equipo. No se impide; si dos equipos activos tienen los mismos tres
  miembros, el listado los marca como «repetido».
- El nombre del equipo no se puede repetir.

### Editar un equipo NO cambia a sus clientes

Esto es lo más importante de entender. Cuando se asigna un equipo a un cliente, sus
tres nombres quedan **copiados** en la ficha: es una foto del momento.

Editar un equipo (cambiarle el AT, por ejemplo) **no** reescribe a los clientes que
ya lo tenían. Es a propósito: un informe de marzo tiene que seguir diciendo quién
estaba en marzo.

Para que un equipo editado se refleje en sus clientes hay una acción explícita:
**Actualizar las asignaciones**, desde el listado de Equipos (el botón de
actualizar de cada fila). Antes de confirmar dice a cuántos clientes afecta, y
reescribe los tres nombres de ésos y su asignación AT vigente.

### Columnas del listado

Equipo, Comercial, Diseñador, AT, Clientes (cuántos tiene asignados), Estado,
Acciones.

---

## 4. Productos (`/productos`)

| Acción | Ruta |
|---|---|
| Listar / buscar / filtrar | `GET /productos` |
| Nuevo producto | `GET /POST /nuevo-producto` |
| Editar producto | `GET /POST /editar-producto/{id}` |
| Eliminar producto | `POST /eliminar-producto/{id}` |
| API búsqueda | `GET /api/productos/search?q=...` |
| API detalle | `GET /api/productos/{et_number}` |
| API crear | `POST /api/productos/crear` (JSON) |

Campos: nombre, Nº ET, material, ruta de fabricación, dimensiones (L/A/H), estado.

---

## 5. Maquinaria (`/maquinaria`)

| Acción | Ruta |
|---|---|
| Listar / filtrar | `GET /maquinaria` |
| Nueva máquina | `POST /nuevo-maquinaria` |
| Editar máquina | `GET /editar-maquinaria/{id}` y `GET /editar-maquinaria/{id}/partial` |
| Guardar edición | `POST /editar-maquinaria/{id}` |
| Eliminar máquina | `POST /eliminar-maquinaria/{id}` |

Campos: Nº serie, modelo, marca, planta asignada, tipo, línea, estado, estado de relevamiento, cliente asociado.

---

## 6. Visitas Técnicas V2 (`/visitas2`)

Formulario SKA-DES-FO-001 Rev.2, completamente dinámico.

| Acción | Ruta |
|---|---|
| Listar visitas | `GET /visitas2` (paginated) |
| Nueva visita | `GET /POST /visitas2/nueva` |
| Editar visita | `GET /POST /visitas2/{id}/editar` |
| Eliminar visita | `POST /eliminar-visita2/{id}` |

### Campos del formulario V2:
- **Participantes:** SWA y CLIENTE (dinámicos, mínimo 1 cada uno)
- **Cliente:** obligatorio (requerido)
- **Asistente Técnico (AT):** obligatorio (requerido)
- **Fecha:** obligatoria
- **Objetivo:** checkboxes (visita programada, No conformidad, seguimiento, solicitud)
- **Tablas 5–9:** filas dinámicas con inputs/textareas/selects
  - 5. Seguimiento últimas visitas / No conformidades
  - 6. Calidad: Consultas / No conformidades (TEMA: select desde `quality_topics`)
  - 7. Asistencia Técnica (Sólo oportunidades) (TEMA: select desde `quality_at_topics`)
  - 8. Conclusiones
  - 9. Acciones
- **Anexos:** múltiples, cada uno con:
  - Editor rich text (contenteditable) para desarrollo
  - Hasta 4 fotos por anexo (subida a servidor → archivo JPEG redimensionado)
  - Eliminar anexo individual
- **Observaciones:** solo visibles en edición, ocultas en PDF
- **Firma A.T.:** campo de texto

### Validaciones al guardar:
- Cliente obligatorio
- Asistente Técnico obligatorio
- Fecha obligatoria
- Al menos un objetivo seleccionado
- Mínimo 1 participante SWA con nombre
- Mínimo 1 participante CLIENTE con nombre

### Impresión PDF:
- Botón "Generar PDF" → `window.print()`
- CSS `@media print` oculta botones, bordes de inputs y fondos
- Observaciones: visibles en PDF (sin clase `no-print`)

### Persistencia:
- Datos guardados en SQLite como JSON en columna `form_data`
- Fotos almacenadas como archivos JPEG en `static/uploads/` (redimensionadas a máx. 1200px ancho, calidad 80%)
- Edición restaura todos los datos (tablas, anexos, imágenes)
- Al eliminar, pasa por la papelera (`entity_type: "visit2"`) antes del borrado físico

### Tablas dinámicas 6 y 7:
- Columnas: `PEDIDO` | `TEMA` (select) | `SITUACIÓN ACTUAL` (textarea)
- TEMA poblado desde `quality_topics` (tabla 6) y `quality_at_topics` (tabla 7)
- Columnas IMPACTO y CANT. eliminadas
- Cada tabla con su propia fuente de datos auxiliar
- Tipo de Producto (CAJA/PLANCHA/BANDEJA) y Planta (LAFERRERE/BERNAL/C.SUÀREZ/SUNCHALES): radio buttons

### Seguimiento de Acciones (Tabla 9):
- Al guardar, se sincroniza con `action_plan_tracking` via `sync_action_plan()`
- Borra y re-inserta filas por `source_visit_id` para mantener consistencia

---

## 7. Relevamiento Técnico V1 (`/relevamiento`)

| Acción | Ruta |
|---|---|
| Listar relevamientos | `GET /relevamiento` |
| Ver relevamiento | `GET /relevamiento/{machine_id}/ver` |
| Formulario completo | `GET /relevamiento/{machine_id}` |
| Formulario partial (AJAX) | `GET /relevamiento/{machine_id}/partial` |
| Guardar | `POST /relevamiento/{machine_id}` |
| Reporte | `GET /relevamiento/{machine_id}/reporte` |

Campos: tipo de relevamiento, formado, cierre inferior, observaciones de materiales, etc.

---

## 7b. Relevamiento Técnico V2 (`/relevamiento2`)

Formulario de Relevamiento Técnico con diseño A4, almacenamiento en JSON y papelera.

| Acción | Ruta |
|---|---|
| Listar relevamientos | `GET /relevamiento2` |
| Nuevo relevamiento | `GET /POST /relevamiento2/nuevo` |
| Editar relevamiento | `GET /POST /relevamiento2/{id}/editar` |
| Eliminar relevamiento | `POST /eliminar-relevamiento2/{id}` |

### KPIs (basados en máquinas, responden a filtros):
| Indicador | Cálculo |
|---|---|
| **Pendientes** | Máquinas sin ningún relevamiento |
| **Total Relevados** | Máquinas con al menos un relevamiento |
| **Completados** | Máquinas cuyo último relevamiento está `Finalizado` |
| **En Proceso** | Máquinas cuyo último relevamiento está `En proceso` |

### Filtros:
- Cliente, Asistente Técnico, Planta, Línea
- Los KPIs se recalculan según los filtros aplicados

### Campos del formulario (almacenados en `form_data` JSON):
- **Info Cliente:** cliente (dropdown con cascada a máquinas), planta, máquina, AT — cliente, máquina y AT son **obligatorios**
- **Especificaciones de Maquinaria:** capacidad, PPM, formato PPM, tipo impresión, slotter, observaciones
- **Estación 1 (Alimentación/Feeder):** toma de cajas, tipo vacío, ventosas, centerline, SQT, criticidad, FODA, **hasta 4 fotos**
- **Estación 2 (Formado y Escuadrado):** tipo formado, cierre inferior, vacío, ventosas, **hasta 4 fotos**
- **Estación 3 (Sistema de Cierre):** Hotmelt o Cinta con sub-secciones y SQT, **hasta 4 fotos**
- **Equipo de Producción:** filas dinámicas (nombre, rol, observaciones)
- **Resumen Final**

### Validación en estaciones:
- Si Centerline o Requiere SQT está marcado → FODA es obligatorio y criticidad se fuerza a ALTA
- Si Requiere SQT está marcado → SQT min y max son obligatorios; SQT nominal se auto-calcula como `(min + max) / 2`

### Fotos por estación:
- Subida a servidor (`POST /upload-foto`) → archivo JPEG redimensionado (máx 1200px ancho, calidad 80%)
- Almacenadas como ruta de archivo en `form_data` (no base64)
- Al eliminar una foto o borrar el relevamiento, se limpia el archivo del disco

### Características:
- Diseño A4 imprimible con estilo `ska-*`
- Save modal: "Guardar y finalizar" / "Guardar y seguir editando" / "Cancelar"
- `disableForm()` para relevamientos finalizados (solo lectura + PDF)
- Al eliminar, pasa por la papelera (`entity_type: "survey2"`) antes del borrado físico
- Listado resistente a eliminación de datos referenciados (usa `form_data` como respaldo)

---

## 8. Minutas de Reunión (`/minutas`)

Formulario de Minuta de Reunión de Equipo (código SKA-MIN-FO-001 Rev.1), diseño A4 imprimible.

| Acción | Ruta |
|---|---|
| Listar minutas | `GET /minutas` (paginated) |
| Nueva minuta | `GET /POST /minutas/nueva` |
| Editar minuta | `GET /POST /minutas/{id}/editar` |
| Eliminar minuta | `POST /eliminar-minuta/{id}` |

### Campos del formulario:
- **1–3:** Fecha, Hora Inicio, Hora Fin — todos obligatorios
- **4.** Lugar / Modalidad — obligatorio
- **5.** Tipo de Reunión — obligatorio (select: Regular, Extraordinaria, Seguimiento, Planificación, Resolución de problemas, Otro)
- **6.** Objetivo de la Reunión — textarea obligatorio con auto-resize
- **7.** Participantes: Presentes y Ausentes (filas dinámicas con nombre)
- **8.** Agenda / Orden del Día — filas dinámicas (Tema, Responsable, Tiempo) con encabezados de columna
- **9.** Desarrollo de la Reunión — editor contenteditable con auto-resize
- **10.** Acuerdos y Decisiones — tabla dinámica con auto-resize en textareas
- **11.** Tareas Asignadas — tabla dinámica (Tarea, Responsable, Plazo, Estado) con auto-resize
- **12.** Próxima Reunión — fecha obligatoria
- **13.** Redactó Minuta — obligatorio
- **Firma Responsable** — obligatorio

### Auto-resize:
Todos los textareas (objetivo, tema, responsable, acuerdo, observaciones, tarea) y el editor de desarrollo se expanden automáticamente al escribir.

### Validaciones:
- Todos los campos estáticos son obligatorios (HTML `required` + `checkValidity()` en submit)
- Save modal: "Guardar y finalizar" / "Guardar como borrador" / "Volver"

### Persistencia:
- Datos guardados como JSON en columna `form_data` de `meeting_minutes`

---

## 9b. Importar desde Excel (`/importar`)

Carga masiva de **clientes** y **máquinas** desde una planilla `.xlsx`. El flujo es
en dos pasos: se sube el archivo, se muestra una previsualización de lo que se
importaría y de lo que no, y recién ahí se confirma. **La previsualización no escribe
nada.**

| Acción | Ruta |
|---|---|
| Descargar la plantilla | `GET /importar/plantilla/{tipo}` |
| Previsualizar (sube el archivo) | `POST /importar/previsualizar` |
| Confirmar | `POST /importar/confirmar` |

Los encabezados se buscan por nombre: no importa el orden ni si están en mayúsculas.

### Columnas de clientes

Nombre (obligatoria), Planta, Sector industrial, **Equipo**, Asesor comercial,
Asistente técnico, Diseñador, Dirección, Ciudad, Estado, Observaciones.

### La columna Equipo

Cuando está, **manda ella**: el cliente se asigna a ese equipo y sus tres integrantes
se copian a la ficha. Las columnas Asesor comercial / Asistente técnico / Diseñador
se mantienen para que las planillas que ya se usan sigan funcionando, pero si la fila
nombra un equipo, se ignoran.

Tres casos:

- **El equipo existe** → se asigna. Si la fila además trae los tres nombres y no
  coinciden con el equipo, se **avisa** y manda el equipo.
- **No existe, pero la fila trae los tres nombres** → se crea el equipo con esos tres
  y se asigna. Se avisa con qué nombre quedó.
- **No existe y le faltan nombres** → la fila se **rechaza**, con el motivo. No se
  arma un equipo a medias.

Sin la columna Equipo se resuelve —o se crea— el equipo a partir de los tres nombres,
como antes.

### Errores y avisos son distintos

La previsualización muestra por separado:

- **Errores** — filas que **no** se van a importar, con el motivo (falta el nombre,
  el cliente ya existe, está repetido en la planilla, el equipo no existe y faltan
  miembros).
- **Avisos** — filas que **sí** se importan, con algo que conviene mirar (la columna
  Equipo pisó a los tres nombres, o el equipo se creó con otro nombre).

Mezclarlos haría creer que una fila que entra se descartó.

---

## 10. Infraestructura y Logística (`/relevamiento-infraestructura`)

| Acción | Ruta |
|---|---|
| Listar | `GET /relevamiento-infraestructura` |
| Nuevo | `GET /relevamiento-infraestructura/nuevo` |
| Editar | `GET /relevamiento-infraestructura/{id}` |
| Guardar crear/editar | `POST /relevamiento-infraestructura` y `POST /relevamiento-infraestructura/{id}` |
| Reporte | `GET /relevamiento-infraestructura/{id}/reporte` |
| Eliminar | `POST /relevamiento-infraestructura/eliminar/{id}` |

Secciones: Almacenamiento, Empaque, Paletizado, Logística (cada una como JSON independiente).

---

## 10b. Agenda de Visitas (`/agenda`)

| Acción | Ruta |
|---|---|
| Vista calendario | `GET /agenda` — FullCalendar integrado |
| Visitas del calendario | `GET /api/visitas-agenda?start=...&end=...&cliente=...` |
| Cancelar visita | `POST /api/agenda/cancelar-visita/{id}` |
| Crear visita rápida | `POST /api/agenda/crear-visita` — desde el calendario |

- Mapeo cliente→AT desde `ATAssignment` vigentes con fallback a `Customer.technical_advisor`
- Las visitas se muestran por fecha en el calendario con estado y asesor

---

## 11. Control de Asignación AT (`/control-at`)

| Acción | Ruta |
|---|---|
| Listar asignaciones | `GET /control-at` (paginado, con filtros) |
| Nueva asignación (modal) | `POST /api/customers/quick-create` (JSON) |
| Editar asignación (modal) | `POST /api/customers/{id}/update-kpis` (JSON) |
| Eliminar asignación | `POST /eliminar-asignacion/{id}` |
| KPIs AT (tabla resumen) | `GET /kpis-at` — tabla de asignaciones con totales |
| API datos KPIs | `GET /api/kpis-at/data` — JSON con table_data, stats, advisors, customer_names |

### Notas técnicas
- Los filtros de visitas usan `form_data["cliente_id"].as_string()` (SQLite json_extract devuelve texto; no usar `.as_integer()` para filtros `in_()`)
- `unique_assignments` se deduplica por `assignment_id` para evitar multiplicación de filas cuando varios clientes comparten nombre (MONDELEZ, UNILEVER, etc.)
- `filtered_customer_ids` se obtiene desde `Customer.id` filtrando por nombres con AT, expandiendo a todos los IDs de cliente que comparten nombre

### Indicadores (8 tarjetas KPI)
| Indicador | Descripción |
|---|---|
| Clientes | Total de clientes (según filtros) |
| Visita Estándar | Suma de visitas estándar asignadas |
| Visita Premium | Suma de visitas premium asignadas |
| Total Visitas Asignadas | Estándar + Premium |
| Visita Finalizada | Visitas realizadas (desde TechnicalVisit2) |
| Visita Pendiente | Asignadas − Realizadas |
| Visita Fuera de Cronograma | Clientes con estado `Fuera de Cronograma` |
| Avance | % de realizadas sobre asignadas (con barra de progreso) |

### Filtros
- Cliente (texto), AT (select), Estándar/Premium (número), Estado (Activo/Inactivo/Fuera de Cronograma)

### Columnas de la tabla
Cliente, AT, Estado (badge), Estándar, Premium, Total, Realizadas, Pendientes, Acciones

### Modal de asignación
Campos: Cliente, **Planta**, AT Asignado, Visitas Estándar, Visitas Premium, Estado.

**La asignación es de una planta, no del cliente entero.** Al elegir el cliente se
cargan sus plantas en un segundo selector. Un cliente con tres plantas tiene tres
asignaciones, una por planta, y cada una puede tener un AT distinto.

Por eso el listado muestra **una fila por cliente y planta**, con la planta debajo
del nombre: antes se unía sólo por nombre de cliente y un cliente con varias plantas
mostraba una sola fila, con la planta que ganara el desempate y un único AT para
todas.

Asigna a cada planta: asesor técnico, visitas estándar/premium, y estado de
seguimiento.

---

## 12. Seguimiento de Plan de Acción (`/seguimiento-plan`)

| Acción | Ruta |
|---|---|
| Listar | `GET /seguimiento-plan` |
| Editar tarea | `POST /seguimiento-plan/{id}/editar` |
| Eliminar tarea | `POST /seguimiento-plan/{id}/eliminar` |

Estados: Pendiente → En curso → Finalizado / Cancelado.

---

## 13. Configuración (`/configuracion`)

CRUD de todas las entidades auxiliares (catálogos):
- Asesores técnicos, diseñadores, asesores comerciales
- Sectores industriales, tipos de máquina, tópicos de visita
- Tipos de formado, tipos de cierre inferior, nombres de cliente/planta
- Plantas distribuidoras, tipos de visita
- Temas de Calidad (tabla 6 del formulario V2)
- Calidad AT (tabla 7 del formulario V2)
- Nombres de Contacto (`ContactName`) — usado en dropdown "Nombre Completo" del equipo del cliente
- Sector / Departamento (`MemberSector`) — usado en dropdown "Sector/Departamento" del equipo del cliente

> Todos los valores se almacenan automáticamente en **MAYÚSCULAS** (validación a nivel modelo, ruta API y seed data).

---

## 14. Papelera (`/papelera`)

| Acción | Ruta |
|---|---|
| Listar elementos eliminados | `GET /papelera` |
| Restaurar elemento | `POST /papelera/restaurar/{id}` |
| Ver detalle | `GET /papelera/detalle/{id}` |

Sistema de "papelera" (soft delete): los elementos se guardan en `trash_items` con el JSON completo antes de ser eliminados de su tabla original.

Tipos de entidad registrados:
| `entity_type` | Origen |
|---|---|
| `customer` | Clientes |
| `machine` | Máquinas |
| `product` | Productos |
| `visit` | Visitas Técnicas V1 (infraestructura) |
| `visit2` | Visitas Técnicas V2 |
| `survey2` | Relevamientos Técnicos V2 |
| `infrastructure` | Relevamiento Infraestructura |
| `auxiliary` | Tablas auxiliares (catálogos) |
| `assignment` | Asignaciones AT |

Filtros en la UI: Todos, Clientes, Máquinas, Productos, Visitas, Visitas V2, Relevamientos V2, Infraestructura, Tablas Auxiliares.

---

## 15. APIs Auxiliares

### Clientes
- `GET /api/cliente-plantas/{customer_name}` — Plantas de un cliente
- `GET /api/plantas-lineas/{customer_name}/{plant}` — Líneas de una planta
- `GET /api/linea-maquinas/{customer_name}/{plant}/{line}` — Máquinas de una línea
- `GET /api/planta-maquinas/{customer_name}/{plant}` — Máquinas de una planta

### Productos
- `GET /api/productos/search?q=...` — Búsqueda de productos
- `GET /api/productos/{et_number}` — Detalle por ET
- `POST /api/productos/crear` — Crear desde JSON

---

## Navegación (Sidebar)

El menú se arma desde el catálogo de módulos (`services/permisos.py`) y **se filtra
por lo que ve cada usuario**: un usuario común sólo ve las pantallas que tiene
marcadas.

### Análisis
- KPIs - AT (`/`)
- KPIs Calidad AT (`/kpi-calidad`)
- KPIs Asignación AT (`/control-at`)
- Historial Asignación AT (`/historial-at`)

### Operaciones
- Biblioteca de Clientes (`/clientes`)
- Organigrama (`/organigrama`)
- Equipos (`/equipos`)
- Biblioteca de Productos (`/productos`)
- Biblioteca de Máquinas (`/maquinaria`)

### Gestión
- Relevamiento Técnico (`/relevamiento2`)
- Visitas Técnicas (`/visitas2`)
- Minutas (`/minutas`)
- Infraestructura & Logística (`/relevamiento-infraestructura`)
- Seguimiento Plan (`/seguimiento-plan`)
- Agenda de Visitas (`/agenda`)
- Historial de cambios (`/historial-cambios`)
- Importar desde Excel (`/importar`)
- Tablas Auxiliares (`/configuracion`)

### Administración (sólo administradores)
- Papelera (`/papelera`)
- Usuarios (`/auth/usuarios`)

---

## Seguridad

- **CSRF:** tokens JWT por usuario, validados en cada POST/PUT/DELETE
- **CSP:** Content-Security-Policy con nonce para scripts
- **Contraseñas:** hasheadas con bcrypt
- **Cookies:** HttpOnly, SameSite=lax
- **Roles:** admin puede todo; user tiene acceso limitado
- **Rutas públicas:** solo `/auth/login` y `/auth/logout`

---

## Soft Delete

Todas las entidades del sistema usan **soft delete** con las columnas:
- `is_active` (Boolean, default True) — indica si el registro está activo
- `inactivation_reason` (Text, nullable) — motivo obligatorio al desactivar
- `inactivated_by_id` (Integer, nullable) — usuario que desactivó
- `inactivated_at` (DateTime, nullable) — cuándo se desactivó

### Comportamiento
- "Eliminar" siempre es `UPDATE is_active = False` (nunca `DELETE FROM`)
- El usuario debe ingresar un motivo obligatorio en un modal antes de desactivar
- Los registros inactivos se muestran en la UI con opacidad reducida y badge rojo "INACTIVO"
- No se pueden editar registros inactivos
- Solo el admin puede reactivar un registro
- Los indicadores e históricos siguen viendo los registros inactivos (las FK no se rompen)

### Entidades afectadas
Clientes, productos, máquinas, visitas técnicas (V2), relevamientos (V1 y V2), asignaciones AT, infraestructura, minutas, y las 14 tablas de catálogos (técnicos, diseñadores, sectores, etc.).

---

## ATAssignment — Versionado (SCD Tipo 2)

Las asignaciones de Asistencia Técnica usan **Slowly Changing Dimension Type 2**:
- `valid_from` (DateTime) — inicio de vigencia
- `valid_to` (DateTime, nullable) — fin de vigencia; `NULL` = vigente

Al editar una asignación existente, la fila vigente se cierra (`valid_to = now`) y se crea una nueva versión. La tabla `/control-at` muestra solo vigentes. Los KPIs suman histórico cuando se filtra por AT.

Al crear un cliente desde `/clientes`, se genera automáticamente su asignación AT.

---

## Archivos eliminados (código muerto)

| Archivo | Motivo |
|---|---|
| `migrate_relevamiento.py` | Script de migración one-time ya ejecutado |
| `templates/relevamiento_lista.html` | Template huérfano (ruta redirige a `/relevamiento2`) |

---

## Estructura del Proyecto

```
├── main.py                  # Punto de entrada, middlewares, routers
├── models.py                # Modelos SQLAlchemy
├── database.py              # Conexión SQLite + sesión
├── enums.py                 # Enums de estado
├── config.py                # Configuración (variables de entorno)
├── security.py              # JWT, CSRF, bcrypt
├── logger.py                # Logging
├── schemas/                 # Pydantic schemas
├── routers/                 # Handlers por módulo
├── services/                # Lógica de negocio
├── templates/               # Jinja2
├── static/                  # CSS, JS, fonts locales
│   └── uploads/             # Fotos subidas (relevamiento2/, etc.)
├── alembic/                 # Migraciones
├── tests/                   # Tests
└── docs/                    # Documentación
```

---
