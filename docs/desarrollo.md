# Desarrollo

Cómo levantarlo, cómo trabajar y qué tener en cuenta para no pisar las trampas que
este proyecto ya pisó.

Para entender cómo está armado, primero [arquitectura.md](arquitectura.md).

---

## 1. Lo que hace falta

| | |
|---|---|
| Python | 3.12 (es lo que corre el CI; el proyecto usa sintaxis de 3.10+) |
| PostgreSQL | 16 o superior, **también en desarrollo** |
| Node.js | sólo para recompilar el CSS de Tailwind y regenerar íconos |
| Google Chrome | sólo para las pruebas de impresión (se omiten si no está) |

**PostgreSQL no es opcional.** El proyecto no soporta SQLite: lo que se prueba tiene
que ser lo que corre en el servidor. Un `create_all` silencioso enmascaró durante
mucho tiempo que las migraciones no reproducían el esquema real.

## 2. Puesta en marcha

```bash
git clone https://github.com/juan-antonio-gonzalez/CRM_AT.git
cd CRM_AT

python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

cp deploy/env.example .env           # y editá SECRET_KEY, DATABASE_URL y ADMIN_PASSWORD
```

La base:

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE crm_at LOGIN PASSWORD 'crm_at';
CREATE DATABASE crm_at OWNER crm_at;
CREATE DATABASE crm_at_test OWNER crm_at;   -- para las pruebas
SQL
```

El esquema y los datos iniciales:

```bash
alembic upgrade head
python main.py seed                  # catálogos + administrador
python main.py seed --demo           # además, datos de demostración
```

Y a correr:

```bash
uvicorn main:app --reload
```

Queda en <http://127.0.0.1:8000>, con el usuario de `ADMIN_USERNAME` (por defecto
`admin`) y la contraseña de `ADMIN_PASSWORD`.

> **`uvicorn main:app` no aplica migraciones a propósito.** El entrypoint de
> producción es `run.py`, que sí las aplica. Así el servidor de desarrollo no toca
> el esquema por sorpresa.

### El CSS y los íconos

```bash
npm install            # una vez
npm run watch:css      # mientras trabajás: recompila al guardar
npm run build:css      # antes de commitear
bash deploy/subset-iconos.sh   # si agregaste un ícono nuevo
```

## 3. La línea de comandos

```bash
python main.py check-schema   # qué revisión de Alembic está aplicada
python main.py seed           # catálogos + administrador (idempotente)
python main.py seed --demo    # + datos de demostración
python main.py create-admin   # sólo el administrador, si no existe
```

`seed` es idempotente: se puede correr las veces que haga falta.

## 4. Pruebas

```bash
# Todo menos la evaluación (sin clave, sin red, sin costo)
pytest

# Sólo un archivo
pytest tests/test_permisos.py -q

# La evaluación real de Caty: llama a la API de DeepSeek y cuesta dinero
DEEPSEEK_API_KEY=... pytest -m eval tests/test_agente_eval.py
```

Las pruebas usan `DATABASE_URL` apuntando a **otra base** (`crm_at_test`) y la
vacían entre pruebas. Si no la definís, `tests/conftest.py` la deriva de la de
desarrollo agregando `_test`.

### Qué necesita cada grupo

| Grupo | Necesita | Sin eso |
|---|---|---|
| La mayoría | PostgreSQL | se saltean o fallan |
| `test_impresion_*`, `test_iconos.py` | Chrome + `pypdf` | se **omiten** solas |
| `test_agente_eval.py` (`-m eval`) | `DEEPSEEK_API_KEY` | se omite |

Las que necesitan base llevan la marca `@requiere_base`, que se saltea si no hay
PostgreSQL. Eso permite correr la mitad rápida de la suite en cualquier máquina.

### Las herramientas de verificación

No son pruebas unitarias: renderizan cosas en un navegador real y las miden. Sirven
para verificar lo que no se ve leyendo el código.

```bash
python tests/pdf_informe.py              # imprime el informe de visita y lo mide
python tests/pdf_cliente.py              # el informe de cliente en hojas A4
python tests/pdf_minuta.py               # la minuta, y comprueba que serialice bien
python tests/iconos_subset.py            # dibuja la fuente y detecta glifos faltantes
python tests/iconos_subset.py --captura  # además deja la lámina para mirar
python tests/captura.py pagina.html salida.png 1400   # captura una página cualquiera
```

Las tres de PDF no llevan argumentos: renderizan la plantilla con datos de prueba,
imprimen con Chrome y comprueban el resultado. Devuelven 0 si está bien, y dejan el
PDF en el directorio temporal para poder mirarlo.

## 5. Agregar una pantalla

El orden importa: hay pruebas que fallan si te saltás un paso, y eso es a propósito.

1. **El router.** Un archivo en `routers/` (o una ruta en uno existente) que
   devuelve `templates.TemplateResponse`. Nada de lógica de negocio acá.
2. **El servicio.** Si hay reglas o consultas no triviales, van en `services/`.
3. **La plantilla.** En `templates/`, heredando de `layout.html`. Usá los macros de
   `_ui.html` (botones, modales, indicadores) y los tokens de color.
4. **El módulo en `services/permisos.py`.** Toda ruta tiene que pertenecer a un
   módulo. La prueba `test_ninguna_ruta_queda_sin_clasificar` falla si no lo hacés,
   y es lo que evita que una pantalla nueva quede abierta para todo el mundo.
5. **El ícono.** Si el módulo usa un ícono nuevo, `bash deploy/subset-iconos.sh`.
   `test_todos_los_iconos_estan_en_el_subset` lo detecta.
6. **El caso de evaluación.** `tests/test_agente_eval.py` exige al menos una
   pregunta por pantalla: Caty tiene que poder hablar de lo que agregaste.
7. **La documentación.** `docs/funcionalidades.md` es una de las fuentes del
   conocimiento de Caty: si la pantalla tiene reglas, tienen que estar ahí.

## 6. Migraciones

```bash
alembic revision -m "descripción"     # a mano, es lo habitual
alembic revision --autogenerate -m "..."   # y revisá SIEMPRE lo que generó
alembic upgrade head
```

Reglas:

- **Idempotentes.** El `upgrade` comprueba si la columna existe antes de agregarla:
  el servidor las corre en cada arranque.
- **Con `downgrade` de verdad.** Aunque casi nunca se use.
- **Un solo head.** Hay una prueba que falla si la cadena se bifurca.
- **Alembic, nunca `create_all`.**

`tests/test_schema.py` verifica que los modelos y las migraciones coinciden. Si
cambiás un modelo y no generás la migración, falla.

## 7. Convenciones

- **Todo en español**: nombres de funciones, variables, comentarios, mensajes de
  error y commits. Los términos técnicos se mantienen en inglés.
- **Los comentarios explican por qué, no qué.** Este proyecto tiene una regla no
  escrita pero constante: si una línea parece rara, al lado está el motivo —y a
  veces la medición que lo respalda—. Es lo que evita que alguien "limpie" una
  decisión deliberada.
- **Un commit por cambio con sentido**, con un mensaje que diga qué se veía mal y
  qué se cambió para arreglarlo.
- **El lenguaje visual es un sistema.** Antes de inventar una clase, mirá
  `tailwind.config.js` y `templates/_ui.html`.

## 8. Las trampas

Están todas documentadas porque ya costaron tiempo. Vale la pena leerlas antes de
tocar la interfaz.

| Trampa | Qué pasa | Cómo se evita |
|---|---|---|
| Un ternario de Jinja sin `{{ }}` dentro de un `class` | El texto `if x else` queda como **nombre de clase** y el estilo no se aplica. No hay error. | `test_los_ternarios_de_jinja_dentro_de_un_class_tienen_llaves` |
| Un `data-*` de modal inventado | El botón no hace nada: el controlador escucha `data-modal-open` / `data-modal-close`. | `test_los_atributos_de_modal_son_los_que_entiende_el_controlador` |
| Un ícono que no está en la fuente | Se imprime el **nombre** del ícono en lugar del dibujo. En el menú, como un título enorme. | `bash deploy/subset-iconos.sh` + `test_todos_los_iconos_estan_en_el_subset` |
| Cambiar un estático sin recompilar | El navegador sigue con el viejo. | `static_url()` agrega `?v=<hash>`; las fuentes llevan además su propia huella |
| Un POST sin `csrf_token` | El middleware redirige al login, y `TestClient` sigue la redirección: la prueba "pasa" sin probar nada. | Usar `follow_redirects=False` y un token real |
| `create_all` en vez de Alembic | El esquema de desarrollo no es el de producción, y el despliegue limpio falla. | Nunca `create_all`; lo verifica `test_schema.py` |
| Un modal escrito a mano | Se desalinea del componente: tamaños, cierre con Escape, foco. | Usar `{% call modal(...) %}` de `_ui.html` |
| `darkMode: false` en Tailwind v3 | Se interpreta como `media`: las clases `dark:` se generan y la interfaz se ve a medio pintar. | `darkMode: "class"` y ninguna clase `dark:` |
| `"/".rstrip("/")` | Devuelve **cadena vacía**, no `/`. La raíz no coincidía con nada. | Normalizar con `or "/"` |
| Editar un equipo esperando que cambien sus clientes | La asignación es una foto: no cambia. | Usar «Actualizar las asignaciones» |

## 9. Antes de abrir un pull request

```bash
npm run build:css
bash deploy/subset-iconos.sh      # si tocaste íconos
pytest                            # sin la evaluación
```

Si tocaste la interfaz, **miralo en el navegador**. Varios de los errores más caros
de este proyecto no se veían leyendo el código: aparecieron midiendo la página
renderizada. Para eso están `tests/captura.py` y los sondeos de PDF.
