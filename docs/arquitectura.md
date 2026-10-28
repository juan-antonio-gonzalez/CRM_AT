# Arquitectura

Cómo está armada la aplicación y por qué. Está escrito para que alguien que llega
nuevo pueda ubicarse en una lectura, y para que las decisiones que parecen raras
tengan su motivo a mano.

Si vas a tocar código, el complemento de este documento es
[desarrollo.md](desarrollo.md). Si vas a desplegarlo, [DEPLOYMENT.md](../DEPLOYMENT.md).

---

## 1. Qué es

Una aplicación web de servidor con renderizado en el servidor. **No hay SPA ni
framework de frontend**: el navegador pide una página, el servidor arma el HTML con
Jinja2 y devuelve todo listo. El JavaScript del navegador es pequeño y puntual
(modales, búsquedas incrementales, el panel de la asistente).

Eso es deliberado y tiene consecuencias prácticas:

- **No hay compilación de frontend.** Tailwind se compila a un CSS estático; el
  resto es HTML y JS servido tal cual.
- **No hay dependencias de red en el navegador.** Nada de CDN ni Google Fonts: las
  fuentes y los íconos están vendorizados en `static/`.
- **Los formularios funcionan sin JavaScript.** Los modales no, pero los formularios
  envían por POST normal.

## 2. Las piezas

```
Navegador
   │  HTTPS
   ▼
Nginx  ──►  uvicorn (2 workers)  ──►  FastAPI
   │                                    │
   │                                    ├── middlewares (seguridad, sesión, CSRF, permisos)
   │                                    ├── routers         ← HTTP: lee el pedido, valida, responde
   │                                    ├── services        ← lógica de negocio y consultas
   │                                    ├── models          ← SQLAlchemy
   │                                    └── templates       ← Jinja2
   │                                          │
   └── static/  (CSS, JS, fuentes, íconos) ◄──┘
                                              │
                                       PostgreSQL
```

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| HTTP | `routers/` | Recibir el pedido, validar la entrada, llamar a un servicio, devolver HTML o redirección. **No** debería tener reglas de negocio. |
| Negocio | `services/` | Las reglas y las consultas. Es donde vive la lógica que se prueba sin levantar HTTP. |
| Datos | `models.py`, `alembic/` | Tablas y migraciones. |
| Presentación | `templates/` | Jinja2. Heredan de `layout.html` o son autocontenidas (login, presentación). |
| Estático | `static/` | CSS compilado, JS, fuentes, íconos, imágenes. |

### Carpetas

```
main.py              arranque, middlewares, manejadores de error, CLI
run.py               entrypoint de producción: migra y levanta uvicorn
config.py            settings (pydantic-settings); normaliza DATABASE_URL
database.py          engine y sesión de SQLAlchemy, get_db
models.py            todos los modelos
enums.py             vocabularios de estado y su normalización
security.py          hash de contraseñas, JWT, CSRF
templating.py        entorno Jinja2 compartido y globales
routers/             24 módulos de endpoints
services/            lógica de negocio
services/permisos.py catálogo de módulos: menú, casillas y control de acceso
services/agente/     Caty: conocimiento, persona, chat, guard, bitácora
alembic/versions/    migraciones (17)
templates/           plantillas (47)
static/              CSS/JS/fuentes/íconos
deploy/              instalador, systemd, nginx, scripts
tests/               pruebas y herramientas de verificación
docs/                esta documentación
```

## 3. El ciclo de un pedido

Todo pedido pasa por los middlewares **antes** de llegar al router. El orden
importa y no es el orden en que están escritos: Starlette ejecuta el último
registrado primero.

```
1. CORS
2. SecurityHeadersMiddleware   → genera el nonce de CSP, agrega cabeceras
3. auth_csrf_middleware        → sesión, permisos y CSRF  ← el importante
4. router
```

### `auth_csrf_middleware` — qué hace, en orden

Está en `main.py` y es la pieza que más conviene entender.

1. **Lee la sesión** de la cookie (`get_current_user`) y deja en
   `request.state.user` el contenido del token, o `None`.
2. **Genera el token CSRF** del usuario y lo deja en `request.state.csrf_token`
   para que las plantillas lo puedan poner en los formularios.
3. **Corta si no hay sesión**, salvo en las rutas de `PUBLIC_PATHS`. A una API le
   responde 401 JSON; a una navegación, redirección al login.
4. **Trae el usuario de la base** —una sola vez por pedido— cuando hace falta: si la
   dirección pertenece a un módulo (hay un permiso que comprobar) o si la respuesta
   es una página (que arma el menú). Lo deja en `request.state.db_user`.
5. **Comprueba la cuenta y el permiso**: cuenta desactivada → se cierra la sesión;
   dirección de un módulo que el usuario no tiene → 403.
6. **Valida el CSRF** en POST/PUT/DELETE con cuerpo de formulario.

> **Por qué el permiso va acá y no en cada router.** Son más de cien rutas. Una que
> se olvide de pedir el permiso queda abierta, y eso no se nota hasta que alguien
> entra donde no debe. Acá pasa todo, y hay una prueba que exige que **cada ruta de
> la aplicación esté clasificada** (`tests/test_permisos.py`).

> **Por qué el usuario de la base no se trae siempre.** Los endpoints del agente
> (Caty) no tocan la base **a propósito**, y una versión anterior que consultaba en
> cada pedido rompió esa propiedad. La consulta se hace sólo cuando hay algo que
> autorizar o un menú que armar.

### CSRF

Doble envío: el token va en un `<meta name="csrf-token">` y en un campo oculto de
cada formulario. El middleware lo valida **sólo** para cuerpos
`form-urlencoded` y `multipart`.

Los endpoints que reciben JSON (`/api/...`) **no** pasan por esa validación: es una
brecha conocida y deliberada del proyecto original. Los endpoints nuevos que
escriben datos usan formulario justamente por eso.

El token se lee del cuerpo crudo, no con `parse_qs`: con `multipart/form-data`
—cualquier formulario con archivos— `parse_qs` fallaba y la petición pasaba sin
validar.

## 4. Sesión y contraseñas

- **Contraseñas**: bcrypt (`passlib`). Irreversibles; si alguien la olvida, se
  reemplaza, no se recupera.
- **Sesión**: JWT firmado con `SECRET_KEY`, en una cookie `session`. Vida
  `SESSION_EXPIRE_HOURS` (24 por defecto). El token lleva `sub` (id), `username` y
  `role`.
- **`COOKIE_SECURE`** debe ser `true` cuando el sitio va por HTTPS. Si está en
  `true` sobre HTTP, el navegador no manda la cookie y el login no funciona.
- **Desactivar una cuenta la echa en el acto**, porque el middleware lee el usuario
  de la base y comprueba `is_active`.

## 5. Permisos por pantalla

El catálogo vive en `services/permisos.py` y **es la única fuente**: de ahí salen el
menú lateral, las casillas de la pantalla de Usuarios y el control de acceso.

Cada módulo declara su etiqueta, su grupo en el menú, su ícono y **las direcciones
que le pertenecen**. La comparación es por segmentos (`/relevamiento` no alcanza a
`/relevamiento2`) y una ruta puede pertenecer a varios módulos: alcanza con tener
cualquiera.

`users.modulos` guarda la lista. **`NULL` no es lo mismo que `[]`**: `NULL` es «sin
configurar» y ve todo lo que no sea de administración, incluidos los módulos
futuros; `[]` es «ninguna». Los usuarios que ya existían tienen `NULL`, para que
nada cambie para ellos.

Detalle completo en [usuarios-y-permisos.md](usuarios-y-permisos.md).

## 6. Plantillas

- Todas heredan de `layout.html` salvo tres autocontenidas: `login.html`,
  `register.html` y `bienvenida.html` (la presentación pública).
- Los componentes reutilizables están como macros en `templates/_ui.html`: botones,
  modales, indicadores, celdas. **Un modal escrito a mano falla las pruebas**: hay
  una que lo detecta.
- Los colores, tamaños y sombras salen de los tokens de `tailwind.config.js`. No se
  usan los colores por defecto de Tailwind; hay pruebas que lo verifican.
- **Los estáticos llevan huella de caché**: `static_url()` agrega `?v=<hash>`.
  Cambiar un archivo cambia la URL y el navegador lo vuelve a pedir. La `url()` de
  las fuentes lleva además la huella del propio archivo, porque la caché de fuentes
  va por URL y sin eso quedaba pegada la vieja.

## 7. Estáticos e íconos

Todo se sirve desde el propio dominio. Los íconos son **Material Symbols por
ligadura**: el `<span>` contiene el nombre y la fuente lo dibuja. **Si el glifo no
está en la fuente no hay error: se imprime el nombre.** Por eso hay un script que
genera un subset y una prueba que lo verifica dibujándolo.

Detalle en [iconos.md](iconos.md).

## 8. Caty, la asistente de uso

Un agente que responde **sólo** cómo se usa la aplicación.

```
pregunta
  → límite de tasa (memoria, por usuario)
  → normalización
  → clasificador de intención  ──fuera de alcance──► rechazo
  → prompt: prefijo cacheado (mapa del sistema) + turno del usuario
  → stream de tokens
  → verificación de salida     ──sin cita / con canario──► reemplazo o rechazo
  → bitácora
```

- **El conocimiento se genera desde el código**: rutas, plantillas y la
  documentación de `docs/funcionalidades.md`. No hay una lista escrita a mano que se
  desactualice.
- **El prefijo del sistema es idéntico byte a byte** entre consultas: así el caché
  de contexto del proveedor sirve. Por eso los permisos del usuario viajan en el
  turno del usuario y no en el prefijo.
- **Toda respuesta tiene que citar una fuente**; si no, se descarta.
- Hay un **canario** en el prompt: si aparece en la respuesta, el prompt se filtró y
  la respuesta se reemplaza.

Detalle en [especificacion-agente.md](especificacion-agente.md).

## 9. Datos

PostgreSQL es el **único** motor, también en desarrollo y en las pruebas: lo que se
prueba es lo que corre en el servidor.

El esquema se crea **siempre con Alembic**, nunca con `create_all`. Durante mucho
tiempo la aplicación llamaba `create_all` al arrancar, lo que enmascaraba que las
migraciones no reproducían el esquema real y hacía fallar un despliegue limpio. Hay
pruebas que verifican que modelos y migraciones coinciden.

Tabla por tabla en [basededatos.md](basededatos.md).

## 10. Errores

Un manejador global renderiza `error.html` con el código y un mensaje. Las rutas
`/api/` reciben JSON en lugar de HTML. El manejador **nunca** puede fallar por sí
mismo: si la plantilla de error revienta, devuelve texto plano.

## 11. Decisiones que parecen raras, y por qué

| Decisión | Motivo |
|---|---|
| Sin SPA ni framework de frontend | El proyecto es de formularios y listados; un SPA agregaba compilación y estado sin resolver nada. |
| Sin CDN | El navegador no depende de la red de un tercero. |
| Permisos en el middleware | Cien rutas: una que se olvide queda abierta. |
| `NULL` ≠ `[]` en `users.modulos` | Los usuarios que ya existían no podían amanecer sin acceso. |
| El agente no toca la base | Sigue respondiendo aunque la base no esté. |
| La asignación de equipo es una foto | Un informe viejo tiene que decir quién estaba entonces. |
| Página pública de presentación | Un dominio nuevo cuya única página es un login es lo que los filtros corporativos bloquean. |
