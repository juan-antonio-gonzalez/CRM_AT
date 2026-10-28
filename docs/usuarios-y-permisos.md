# Usuarios y permisos

Cada usuario tiene una cuenta y **una lista de pantallas que puede ver**. Un
administrador ve todo y administra las cuentas; un usuario común ve exactamente lo
que tenga marcado.

Se maneja desde **Usuarios** (menú → Gestión → Usuarios), con el botón de editar de
cada fila.

## Una sola fuente

El catálogo de módulos vive en `services/permisos.py` y de ahí salen **tres** cosas:

| Quién lo usa | Para qué |
|---|---|
| `templates/layout.html` | Arma el menú lateral |
| `templates/editar_usuario.html` | Arma los checks de la pantalla de Usuarios |
| `main.py` (el middleware) | Comprueba el acceso a cada dirección |

Tener tres listas separadas garantizaba que tarde o temprano una dijera algo
distinto de la otra. Un check que no coincide con el menú esconde una pantalla que
el usuario igual puede abrir escribiendo la dirección; un menú que no coincide con
el control de acceso muestra una puerta que da a un 403.

Cada módulo declara:

```python
Modulo(
    "clientes", "Biblioteca de Clientes", "Operaciones", "/clientes", "group",
    rutas=("/clientes", "/nuevo-cliente", "/editar-cliente", ...),
    ayuda="Las fichas de los clientes, sus contactos y sus informes.",
)
```

El menú se arma con un bucle sobre esa lista. Agregar una pantalla al menú es
agregar un módulo, no tocar veinte enlaces escritos a mano.

## Esconder el enlace no alcanza

Ocultar una opción del menú no protege nada: la dirección se escribe a mano. La
comprobación va en el **middleware**, no en cada router, porque son más de cien
rutas: una que se olvide de pedir el permiso queda abierta, y eso no se nota hasta
que alguien entra donde no debe.

La comparación es **por segmentos**, no por texto: `/relevamiento` no tiene que
alcanzar a `/relevamiento2`, y `/` sólo vale exacta porque si no se comería todas
las direcciones de la aplicación.

Una ruta puede pertenecer a **más de un módulo** y alcanza con tener cualquiera.
`/api/cliente-plantas/` lo usan el alta de clientes y el alta de asignaciones AT; si
perteneciera a uno solo, el otro tendría una pantalla a medias.

## Los tres estados de un usuario

| `modulos` | Qué ve |
|---|---|
| `None` (sin configurar) | Todos los módulos que no son de administración, **y también los que se agreguen más adelante** |
| `[]` | Nada |
| `['clientes', 'equipos']` | Exactamente ésos |
| *(rol administrador)* | Todo, siempre, sin importar la lista |

`None` no es lo mismo que la lista vacía, y por eso la columna es *nullable*: todos
los usuarios que ya existían tienen `None` y siguen viendo lo de siempre. Si el
valor por defecto hubiera sido `[]`, habrían amanecido sin acceso a nada.

En la pantalla de edición, «Ve todas las pantallas» guarda `None`. Es la opción que
incluye los módulos futuros.

## Lo que no se puede hacer

- **Quitarse el rol de administrador a uno mismo.** Se quedaría sin poder volver a
  entrar a esta pantalla, y no hay forma de arreglarlo desde la aplicación.
- **Asignar un módulo de administración** (`usuarios`, `papelera`). El formulario los
  muestra deshabilitados y el servidor los filtra igual: el formulario se puede
  armar a mano.
- **Repetir un nombre de usuario o un correo.** Se valida contra la base, ignorando
  la propia fila.

## La cuenta desactivada se va enseguida

El middleware lee el usuario de la base en cada pedido, así que desactivar una
cuenta la echa en el acto. Antes, el token seguía sirviendo hasta que venciera.

## Lo que también respeta los permisos

- **El menú lateral**, armado desde el catálogo.
- **Los enlaces de ayuda** entre pantallas. El formulario de cliente ofrece
  «Gestionar equipos»; sin el módulo Equipos, no aparece. Un enlace a una pantalla
  prohibida no es sólo ruido: manda al usuario a un 403.
- **La búsqueda global.** Busca en cuatro grupos y cada uno pertenece a un módulo.
  Un resultado que lleva a un 403 es peor que no mostrarlo.
- **Caty.** En el turno del usuario se le agrega una nota con las pantallas que esa
  cuenta no ve, para que no la mande a un 403. Va ahí y **no** en el prefijo del
  sistema a propósito: el prefijo tiene que seguir siendo idéntico byte a byte
  entre consultas para que el caché de contexto de DeepSeek sirva. Es una ayuda,
  no una barrera: Caty no decide accesos.

## Cómo se verifica

| Archivo | Qué cubre |
|---|---|
| `tests/test_permisos.py` | El catálogo, la comparación por prefijo, los tres estados de usuario y **la cobertura de rutas** |
| `tests/test_permisos_aplicados.py` | Los permisos sobre la aplicación real: 403, el menú, la búsqueda y la edición |

La prueba que más importa es la de cobertura:

```python
def test_ninguna_ruta_queda_sin_clasificar():
    huerfanas = permisos.sin_clasificar(_rutas_de_la_app())
```

Una ruta nueva que nadie clasificó queda **abierta para todo el mundo**, y eso tiene
que ser una decisión, no un olvido. Si esta prueba falla, hay que decidir a
propósito: o la ruta pertenece a un módulo, o va a `RUTAS_LIBRES` con un motivo.

## Lo que apareció al construirlo

**El catálogo abría de más.** El módulo de clientes declaraba el prefijo
`/configuracion` entero para que su formulario pudiera usar el ayudante «crear un
comercial». Eso le abría la pantalla completa de Tablas Auxiliares a quien sólo
necesitaba el ayudante. Ahora declara las cuatro operaciones (`add`, `list`, `edit`,
`delete`) y no el prefijo pelado. Lo encontró la verificación a mano, no las
pruebas: **declarar un prefijo abre todo lo que empiece así**, y conviene declarar
lo más específico que alcance.

**Caty no podía depender de la base.** Los endpoints de Caty no tocan la base a
propósito, y una primera versión del middleware consultaba el usuario en **cada**
pedido: eso rompió esa propiedad y ocho pruebas. Ahora la consulta se hace sólo
cuando hace falta: cuando la dirección pertenece a un módulo (hay un permiso que
comprobar) o cuando la respuesta es una página (que arma el menú). Un endpoint de
API libre no paga el viaje.

**Los íconos del menú dejaron de estar en las plantillas.** Al pasar el menú a un
bucle, `dashboard`, `checklist_rtl` y `manage_accounts` sólo existían en el
catálogo: la primera regeneración de la fuente se los iba a llevar puestos y habrían
vuelto a verse como texto. `deploy/iconos.py` ahora lee el catálogo.
