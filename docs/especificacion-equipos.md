# Especificación — Equipos asignados a clientes

**Estado:** propuesta para revisión. No hay código escrito.
**Reemplaza:** la asignación manual de comercial, diseñador y AT en el alta de cliente.

---

## 1. El cambio

**Hoy.** Cada cliente guarda tres nombres sueltos, elegidos uno por uno con tres
desplegables: `assigned_commercial`, `designer`, `technical_advisor`.

**Después.** El equipo es una entidad propia y reutilizable: se arma una vez con
comercial, diseñador y AT, y al cliente se le asigna **un equipo**.

Consecuencia práctica: cambiar el diseñador de una cuenta deja de ser "elegir tres
personas de tres listas" y pasa a ser "cambiar de equipo".

---

## 2. El hallazgo que simplifica el diseño

**Un cliente con varias plantas no es una fila: son varias filas, una por planta.**

`services/customer_service.py:197` y el alta lo confirman: la pantalla de Nuevo Cliente
permite elegir un cliente existente y una planta nueva, y eso crea **otra fila** con el
mismo `name` y otro `plant`. `get_plant_machines` filtra por `name` **y** `plant`.

Entonces la regla que pediste —un equipo por cliente, y si hay varias plantas uno por
planta— **no necesita ninguna tabla intermedia**: alcanza con una columna `team_id` en la
fila del cliente, porque la fila ya es el par cliente-planta.

```
customers (una fila por cliente+planta)
  id | name        | plant          | team_id
  1  | CARTOCOR    | Planta Norte   | 3        <- Equipo A
  2  | CARTOCOR    | Planta Sur     | 7        <- Equipo B
  3  | CARTOCOR    | Planta Centro  | 3        <- Equipo A
```

---

## 3. La tensión que hay que resolver

**La asignación AT se guarda por nombre de cliente, sin la planta.**
`services/customer_service.py:115` la busca así:

```python
existing_at = db.query(models.ATAssignment).filter(
    models.ATAssignment.customer_name == name,   # <- sin plant
    models.ATAssignment.valid_to.is_(None)
).first()
```

Y `Control de Asignación AT` (`routers/control_at.py:35`) hace el join por
`Customer.name == ATAssignment.customer_name`, y después **descarta filas agrupando por
nombre** (`vistos[r.name]`). O sea: si un cliente tiene tres plantas, Control AT muestra
**una sola fila**, con la planta que haya ganado el desempate y un único AT para todas.

Hoy eso pasa desapercibido porque los tres `technical_advisor` de las plantas suelen ser
el mismo. Con equipos por planta deja de ser cierto: dos plantas con AT distinto no se
pueden representar.

**Hay además una segunda fuente de verdad ya existente:** `customers.technical_advisor`
(por planta) y `at_assignments.technical_advisor` (por cliente) pueden discrepar hoy, y
nada los mantiene sincronizados.

### Decisión: `at_assignments` pasa a ser por planta

Se agrega `plant` a `at_assignments`, y el join de Control AT pasa a ser por
`(customer_name, plant)`. Es lo que hace coherente el modelo completo:

| Dato | Antes | Después |
|---|---|---|
| Quién es el AT | `customers.technical_advisor` (por planta) y `at_assignments.technical_advisor` (por cliente) | El equipo, copiado a los dos |
| Plan de visitas | Por cliente | Por planta |
| Control AT | Una fila por cliente | Una fila por planta |

No es alcance extra: **es tu requisito**. "Cada planta tiene un equipo" no se puede
cumplir sin esto.

**No hay datos que migrar.** La base tiene 0 clientes y 0 asignaciones reales (hay 1 fila
huérfana, sin cliente). Es el único momento en que este cambio sale gratis.

---

## 4. Modelo

### Tabla nueva: `teams`

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | |
| `name` | String, único | El nombre con el que se reconoce el equipo |
| `commercial` | String, **no nulo** | Del catálogo `commercial_advisors` |
| `designer` | String, **no nulo** | Del catálogo `designers` |
| `technical_advisor` | String, **no nulo** | Del catálogo `technical_advisors` |
| `is_active` | Boolean | Baja lógica, como todo lo demás |
| `inactivation_reason`, `inactivated_by_id`, `inactivated_at` | | El patrón que ya usa el proyecto |
| `created_at`, `updated_at` | DateTime | |

Los tres miembros son **no nulos**: pediste que el equipo no pueda estar incompleto, y la
forma de garantizarlo es que la base no lo permita, no una validación de formulario que
alguien puede saltear.

### Columnas nuevas

- `customers.team_id` — Integer, nullable, FK a `teams`.
- `at_assignments.plant` — String, nullable, indexada junto a `customer_name`.

### Las tres columnas del cliente se mantienen

`assigned_commercial`, `designer` y `technical_advisor` **no se borran**. Al asignar un
equipo se copian sus tres nombres a esas columnas.

Es la decisión que hace que este cambio sea chico. Los tres campos se usan **208 veces en
unos 40 archivos** —listados, filtros, KPIs, reportes, la importación de Excel, la
búsqueda—:

| Campo | Usos | Archivos |
|---|---|---|
| `technical_advisor` | 109 | 35 |
| `designer` | 62 | 14 |
| `assigned_commercial` | 37 | 13 |

Si se reemplazaran por un join, habría que tocar los 208 lugares para el mismo resultado
visible. Manteniéndolas, **todo lo que hoy funciona sigue funcionando sin abrirse**: lo
único que cambia es el formulario y la pantalla de equipos.

La tabla de equipos es la fuente de verdad; las columnas del cliente son la copia del
momento en que se asignó.

---

## 5. Semántica: foto, no referencia viva

**Editar un equipo NO cambia a los clientes que ya lo tienen.**

Asignar guarda una foto. Si en marzo el equipo tenía a Pérez y hoy tiene a Gómez, el
informe de marzo tiene que seguir diciendo Pérez.

Con referencia viva, editar un equipo reescribe el pasado de todos sus clientes — y en un
CRM que audita y reporta, eso es un problema, no una comodidad.

Para el caso contrario hay una acción explícita: **"Actualizar las asignaciones de este
equipo"**, que muestra a cuántos clientes afectaría y recién ahí aplica. La corre la
persona, cuando quiere.

---

## 6. Pantallas

### 6.1 Equipos (nueva)

Entrada propia en el menú lateral. No va dentro de Configuración → Tablas Auxiliares:
ese molde maneja catálogos de un solo nombre (`add/list/edit/delete` por tipo), y un
equipo son tres miembros y una baja con consecuencias.

- **Listado:** nombre del equipo, comercial, diseñador, AT, cantidad de clientes
  asignados, estado. Filtro por estado.
- **Alta y edición:** nombre + tres selectores, poblados desde los tres catálogos. Los
  tres obligatorios. Si un catálogo está vacío, se avisa con el enlace para cargarlo.
- **Baja:** lógica, con motivo, a la papelera. Si el equipo tiene clientes asignados, se
  avisa cuántos son antes de confirmar. No se puede eliminar un equipo en uso.

### 6.2 Alta y edición de cliente

Los tres desplegables se reemplazan por **un solo selector de equipo**. Debajo, los tres
miembros en modo lectura, para ver a quién se le está asignando la cuenta antes de
guardar.

**Aplicar a todas las plantas.** Cuando el cliente ya tiene más de una planta, el selector
trae un tilde: *"Aplicar este equipo a todas las plantas de este cliente"*, que muestra
cuántas filas va a cambiar. Sin eso, dejar las tres plantas con el mismo equipo son tres
altas.

### 6.3 Lo que no cambia

Listado de clientes, filtros, búsqueda, KPIs, reportes, papelera, historial y exportación
siguen leyendo las mismas columnas de siempre. **No se tocan.**

---

## 7. La asignación AT automática

Al crear un cliente se genera sola su asignación AT (`customer_service.py:120`). Pasa a:

1. Tomar el AT **del equipo** de esa fila.
2. Guardarla con la `plant` de esa fila.
3. Reemplazar el `technical_advisor` de la asignación si la planta ya existía con otro
   equipo.

---

## 8. Importación de Excel

Hoy mapea columnas a los tres campos sueltos. Pasa a aceptar una columna **`Equipo`**:

- **Si el equipo existe:** se asigna y se copian sus miembros. Si la planilla además trae
  las tres columnas viejas y no coinciden, se avisa y manda el equipo.

  > «Avisar» necesitó un canal propio. Hasta ahora la previsualización tenía un solo
  > canal, `errores`, y su texto dice *«no se van a importar»*. Meter ahí una fila que
  > **sí** entra habría hecho creer lo contrario, así que `validar()` devuelve ahora
  > `(listas, errores, avisos)` y la pantalla los muestra por separado.
- **Si no existe pero la fila trae los tres miembros:** se crea el equipo y se asigna.
- **Si no existe y faltan miembros:** la fila se rechaza con el motivo, como cualquier
  otro error de importación.

No se inventan equipos a partir de un nombre suelto: un equipo a medias es peor que un
error que se ve.

---

## 9. Decisiones que tomé

Las cinco que quedaron a mi criterio, con el motivo:

| # | Decisión | Por qué |
|---|---|---|
| 1 | **Foto, no referencia viva** | Editar un equipo no puede reescribir el pasado de sus clientes |
| 2 | **Los tres miembros obligatorios, garantizado en la base** | "No debe estar incompleto" se garantiza con `NOT NULL`, no con una validación de formulario |
| 3 | **Pantalla propia en el menú** | Un equipo es más que una tabla auxiliar; se asigna, se consulta y tiene consecuencias |
| 4 | **Se puede repetir la misma persona en dos roles** | En una empresa chica el mismo puede ser diseñador y AT. Se avisa en pantalla, no se impide |
| 5 | **La importación crea el equipo sólo si trae los tres miembros** | Evita que un error de tipeo genere un equipo basura que después hay que limpiar |
| 6 | **`Team` no hereda de `BaseCatalogMixin`, hereda de `BaseSoftDeleteMixin`** | Ver abajo |

### Por qué se separaron los mixines

`BaseCatalogMixin` significaba dos cosas a la vez: "tiene baja lógica" y "es un
catálogo de un nombre que se mantiene desde Tablas Auxiliares". Un equipo tiene la
primera y no la segunda.

Heredar del mixín de catálogo habría hecho fallar
`test_catalogos.py::test_todos_los_catalogos_estan_registrados_en_tablas_auxiliares`,
que exige que todo catálogo esté en Configuración. La prueba tenía razón: el
problema era el mixín, que mezclaba dos conceptos.

Ahora `BaseSoftDeleteMixin` tiene las cuatro columnas y `BaseCatalogMixin` hereda
de él agregando el significado de catálogo. Los 16 catálogos existentes no
cambiaron; `Team` tiene las columnas sin ser un catálogo, y la prueba sigue
cuidando lo que dice cuidar.

---

## 10. Fases

| Fase | Entregable | Verificación |
|---|---|---|
| 1 | Tabla `teams` + `customers.team_id` + `at_assignments.plant`, con migración | ✅ hecho — sin deriva (`alembic check` limpio) |
| 2 | Pantalla de Equipos (listado, alta, edición, baja) | ✅ hecho — rechaza el equipo incompleto |
| 3 | Alta y edición de cliente con selector de equipo | ✅ hecho |
| 4 | Asignación AT por planta y Control AT por `(cliente, planta)` | ✅ hecho |
| 5 | Importación con columna `Equipo` | ✅ hecho |
| 6 | "Actualizar las asignaciones de este equipo" + "Aplicar a todas las plantas" | ✅ hecho |

Cada fase queda desplegable. La 1 sola no cambia nada visible; la 3 es la que se nota.

---

## 11. Riesgos

| Riesgo | Mitigación |
|---|---|
| Tocar `at_assignments` arrastra Control AT, KPIs, papelera e historial | La base está vacía: se cambia la estructura sin migrar datos. Fase 4 aislada y verificada |
| Que las columnas del cliente y el equipo se desincronicen | Sólo se escriben las columnas desde la asignación; el equipo no las toca. Y hay una acción explícita para resincronizar |
| Equipos duplicados con los mismos tres miembros | Se avisa al crear uno idéntico a otro existente. No se impide: dos equipos con las mismas personas pueden tener sentido por zona o por turno |
| El catálogo de personas está vacío | La pantalla de Equipos lo detecta y manda a cargarlo primero |

---

## 12. Lo que no entra

- Más de un equipo por cliente o por planta.
- Equipos por línea de producción.
- Historial de cambios de equipo (queda la foto en las columnas, no una traza aparte).
- Que un equipo herede clientes automáticamente al editarlo.


---

## 13. Lo que apareció al construir la fase 3

**La importación de Excel también crea clientes.** Habría dejado clientes con los
tres nombres y sin equipo, que es una inconsistencia silenciosa: la ficha se ve
bien y el vínculo no existe. Ahora la importación **resuelve o crea** el equipo a
partir de los tres nombres de la planilla. Si la planilla no trae los tres, el
cliente se importa igual y queda sin equipo: esas columnas son opcionales desde
siempre y volverlas obligatorias rompería las planillas que ya se usan. La columna
`Equipo` explícita llega en la fase 5.

**Los tests de la aplicación daban de alta clientes con los tres campos sueltos.**
Actualizarlos fue parte del cambio, no un efecto colateral: los tests describen
cómo se usa la aplicación, y eso cambió. Se agregó `tests/apoyo.py` con un equipo
compartido, idempotente, porque `_clean_tables` vacía las tablas después de cada
prueba y el equipo tiene que poder recrearse.

**El modal de edición carga su parcial con `innerHTML`.** Un `<script>` insertado
así no se ejecuta nunca, así que el despliegue de los integrantes del equipo va en
`clientes.html`, dentro de `initializeEditModalScripts()`, y no en el parcial. Hay
una prueba que falla si alguien mueve el script al parcial.

**El AC del equipo se guarda en mayúsculas**, igual que los catálogos de personas.
Un cliente creado antes por el formulario guardaba "Carlos Pérez"; ahora guarda
"CARLOS PÉREZ" porque viene del equipo. Es más consistente, y es un cambio visible
en los listados.


---

## 14. Lo que apareció al construir la fase 4

**La paginación de Control AT contaba versiones, no filas.** El `total` salía del
`count()` del join: un cliente con tres asignaciones históricas daba tres, y
después el deduplicado dejaba una. Paginar con el número inflado mostraba páginas
con menos filas de las pedidas y la última vacía. Era un problema de antes, pero el
cambio a `(cliente, planta)` lo hacía más visible. Ahora el total cuenta
`DISTINCT (cliente, planta)`.

**El alta de asignaciones rechazaba la segunda planta.** `quick_create_assignment`
buscaba duplicados sólo por nombre de cliente, así que un cliente con dos plantas
no podía tener una asignación en cada una: la segunda daba «ya existe una
asignación vigente». Es exactamente lo que la fase viene a resolver, y estaba en el
camino.

**La versión nueva de una asignación perdía la planta.** `update_assignment_kpis`
cierra el período vigente y abre otro copiando `customer_name` y
`technical_advisor`, pero no `plant`. Sin arreglarlo, el primer cambio de visitas
habría hecho que la asignación volviera a valer para todas las plantas del cliente,
deshaciendo el trabajo de la fase en silencio. Hay una prueba que lo cubre.

**El formulario de Control AT no tenía de dónde elegir la planta.** Se agregó un
selector que se carga con el cliente, usando el endpoint `/api/cliente-plantas/`
que ya existía para el alta de clientes. Con una sola planta se elige sola.


---

## 15. Lo que apareció al construir la fase 5

**Un aviso no es un error, y no había dónde ponerlo.** La previsualización de la
importación tenía un solo canal para lo que no entra, y su texto dice «no se van a
importar». Una fila que **sí** se importa pero con la columna `Equipo` pisando a los
tres nombres no entra en ese canal. `validar()` devuelve ahora
`(listas, errores, avisos)`; los avisos salen en un bloque propio, en tono
informativo y no de alerta.

**Los tres nombres del cliente salen del equipo, no de la planilla.** Cuando la fila
nombra un equipo, las columnas `Asesor comercial`, `Asistente técnico` y `Diseñador`
se ignoran a propósito. Si se copiaran las de la planilla, la columna del cliente y
el `team_id` podrían discrepar — que es exactamente el estado del que este proyecto
viene a salir.

**El nombre del equipo se busca normalizado.** `Equipo Norte` en la planilla
encuentra `EQUIPO NORTE` en la base. Sin eso, la columna sería inusable: el modelo
guarda en mayúsculas y la planilla la escribe una persona.


---

## 16. Lo que apareció al construir la fase 6

**La acción de propagar necesitaba decir qué contradice.** «Actualizar las
asignaciones» hace exactamente lo que el resto del diseño evita, así que el modal lo
explica: editar un equipo no cambia a sus clientes *a propósito*, para que un informe
de marzo siga diciendo quién estaba en marzo. El texto viejo de la pantalla de
edición mandaba a reasignar cliente por cliente; ahora manda a esta acción.

**El nombre original hay que leerlo antes de guardar.** «Aplicar a todas las plantas»
busca las hermanas por nombre. Si el usuario renombra el cliente en el mismo guardado,
las otras plantas conservan el nombre viejo y son ésas las que hay que alcanzar. Leer
el nombre después de actualizar no habría encontrado ninguna.

**Queda en el historial.** El cambio toca filas que no son la que se está editando, y
quien lea «editó CARTOCOR» tiene que poder ver que además se cambiaron dos plantas,
sin abrir cada una.

**Y una prueba del proyecto atrapó un `or_` sin importar** en `team_service.py`
(`test_los_modulos_no_usan_nombres_sin_definir`). Habría sido un `NameError` la
primera vez que alguien apretara el botón: ninguna prueba de las que escribí lo
tocaba con base.


---

## 17. El bug que sólo apareció probando a mano

Al terminar la fase 6 hice la verificación que faltaba: crear un equipo, dar de alta
un cliente con **dos plantas**, y mirar. Borré los datos de prueba y el conteo no
cerró: **dos clientes, pero una sola asignación AT**.

`create_customer` buscaba la asignación existente sólo por nombre de cliente. La
segunda planta encontraba la de la primera, no creaba nada, y quedaba sin AT. En
Control AT se veía como una fila con el cliente y la planta en blanco. Era la misma
forma del bug de la fase 4 —buscar por nombre cuando la identidad es nombre **y**
planta— pero en el otro extremo del flujo: allá al editar, acá al crear.

Lo que importa del episodio es por qué las pruebas no lo atraparon.
`test_cambiar_el_equipo_de_una_planta_no_toca_a_las_otras` **ya creaba dos plantas
del mismo cliente** por el mismo camino. Pasaba por el código con el bug y no lo
veía, porque sólo miraba las columnas del `Customer` y nunca la tabla de
asignaciones. La prueba existía; le faltaba la afirmación.

Por eso quedaron dos pruebas nuevas: una que cuenta las asignaciones de un cliente
con dos plantas, y otra que mira la pantalla y exige que las dos filas traigan el AT.

**Lección para el resto:** cada vez que la identidad de una fila pase a ser
`(cliente, planta)`, hay que revisar **todas** las búsquedas por nombre de cliente,
no sólo la que se está tocando. Fueron tres: la del join de Control AT, la del alta,
y la de la edición.
