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

---

## Sistema de diseño

Toda la interfaz sale de dos archivos. Si vas a tocar una pantalla, conviene
leerlos antes: casi todo lo que parece "un detalle de esta pantalla" ya está
resuelto en un token o en un componente.

### Tokens — `tailwind.config.js`

No se usan los colores por defecto de Tailwind. Cada color es un token con
significado, y los tonos `500` están elegidos para pasar contraste AA (4.5:1)
sobre blanco:

| Familia | Ancla | Uso |
| --- | --- | --- |
| `brand` | `navy #00205b`, `sky #08b2ff` | Colores oficiales, tomados del logo |
| `primary` | `#0b3d91` | Acción. Conserva `DEFAULT`: ~980 clases usan `bg-primary` a secas |
| `exito` | `#047857` (5.48:1) | Confirmado, completado |
| `alerta` | `#b45309` (5.02:1) | Pendiente de atención |
| `peligro` | `#b91c1c` (6.47:1) | Error, destructivo |
| `info` | `#0369a1` (5.93:1) | Informativo, en curso |
| `superficie` | `base`, `card`, `suave`, `borde`, `fuerte` | Fondos y bordes |
| `texto` | `fuerte`, `base`, `suave`, `tenue` | Jerarquía de texto |

La escala tipográfica tiene **piso de 12px** (`text-2xs`). No hay texto más chico:
en la auditoría inicial había 780 casos por debajo, varios de 9px.

### Componentes — `templates/_ui.html`

Macros de Jinja. Se importan con
`{% from "_ui.html" import indicador, modal, boton %}`.

- **`indicador(etiqueta, valor, tono, icono)`** — azulejo de métrica. El color va
  en el fondo (tono 100) y en el borde izquierdo (tono 500), no sólo en el borde:
  con el borde solo, doce tarjetas blancas dominaban la pantalla y el conjunto se
  leía gris. Los indicadores sin tema (los totales) quedan en blanco a propósito,
  para que el color signifique algo.
- **`modal(id, titulo, tamano, icono, tono_icono, descripcion)`** — tres tamaños:
  `confirmar` (`max-w-sm`), `formulario` (`max-w-lg`) y `amplio` (`max-w-3xl`). El
  contrato de identificadores está documentado en el propio macro:
  `{{id}}`, `{{id}}-titulo`, `{{id}}-cuerpo`, y así. Se cierra desde el código con
  `window.cerrarModal('{{id}}')`.
- **`estado(...)`**, **`boton(...)`**, **`barra_filtros(...)`**, **`vacio(...)`**.

Un solo controlador en `static/js/app.js` gobierna todos los modales: se abren con
`data-modal-open="<id>"` y se cierran con `data-modal-close="<id>"`. El mismo
controlador cierra con **Escape** y con **clic en el fondo**, para cualquier
elemento con `role="dialog"`.

### Reglas del lenguaje visual

Estas decisiones se tomaron a partir de lo que se veía en pantalla, y hay pruebas
que las sostienen (`tests/test_ui.py`):

1. **Caja de oración, nunca mayúsculas con tracking.** El par MAYÚSCULAS + letras
   separadas es el tell más grande de tablero anticuado; había 860 casos.
2. **La jerarquía la da el espacio y el tamaño, no el borde.** No anidar cajas.
3. **Pocas métricas protagonistas.** Cuatro, con la cifra grande; el resto en una
   fila de detalle sin caja. Doce azulejos iguales no tienen punto focal.
4. **Un panel sin datos explica qué va a aparecer**, no se muestra vacío.
5. **Las fechas se muestran siempre igual** (`dd/mm/aaaa`), sin importar si vienen
   como `date` o como texto ISO.
6. **Los colores salen de los tokens.** Hay una prueba que falla si aparece una
   clase de color fuera del sistema.

### Trampa a tener en cuenta: clases interpoladas

Tailwind busca nombres de clase **literales** en el código. Una clase armada con
Jinja:

```jinja
class="text-{{ color }}-600"
```

nunca aparece como `text-exito-600` en el fuente, así que Tailwind **no genera esa
regla** y el color no se aplica. Las clases que se interpolan de verdad están en la
lista blanca (`safelist`) de `tailwind.config.js`. Si agregás una interpolación
nueva, sumala ahí.

La lista es explícita a propósito: un patrón amplio generaba **756 KB** de CSS en
lugar de 53 KB.

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

## Pruebas

```bash
DATABASE_URL="postgresql://crm_at:crm_at@127.0.0.1:5432/crm_at_test" pytest -q
```

127 pruebas. Las que cubren la interfaz viven en `tests/test_ui.py` y verifican el
lenguaje visual, no el aspecto de una pantalla concreta: que no vuelvan las
mayúsculas con tracking, que los indicadores usen el componente compartido, que los
modales usen uno de los tres tamaños, que no haya texto bajo 12px, que los colores
salgan de los tokens, que las fechas se muestren siempre igual, que las plantillas
cierren todos los `div` y que los estáticos lleven la huella de caché.

Las pruebas de navegador (capturas, PDF de los informes) se omiten si no hay
Chrome; el CI las corre porque ahí sí está disponible.

## Estado de los arreglos

Las correcciones aplicadas sobre la auditoría inicial quedaron documentadas en tres
lugares, según su naturaleza:

- **Decisiones de diseño y su por qué** — en los comentarios de
  `tailwind.config.js`, `templates/_ui.html` y las cabeceras de las plantillas
  principales. Cada una explica qué se veía mal, no sólo qué se cambió.
- **Motivos de despliegue** — en [DEPLOYMENT.md](DEPLOYMENT.md), en particular los
  permisos de archivos y la caché de estáticos, que ya causaron fallas en
  producción.
- **Historial de cambios** — en los mensajes de commit, que incluyen la medición
  que respalda cada arreglo y, cuando corresponde, la corrección de un diagnóstico
  previo que resultó equivocado.

Cuando un arreglo se verificó midiendo en el navegador (geometría de una tabla,
color realmente renderizado, ancho de columnas a distintos tamaños de ventana), la
medición está en el mensaje de commit. Es deliberado: varios de los errores más
costosos de este proyecto **no se veían leyendo el código**, y sólo aparecieron al
medir la página renderizada.

