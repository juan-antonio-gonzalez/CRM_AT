"""Pruebas del modelo de equipos — fase 1.

Todo lo de acá corre sin PostgreSQL. La verificación de deriva completa
—comparar el esquema que produce Alembic contra los modelos— vive en
`test_schema.py` y necesita la base; acá se adelanta la parte que se puede
comprobar leyendo el código, que es la que detecta el error temprano.

El caso que estas pruebas protegen es concreto: agregar una columna al modelo y
olvidarse de la migración. `test_schema.py` lo agarra, pero sólo con PostgreSQL
levantado; acá se agarra siempre.
"""

import ast
import datetime
import os
import re
import glob

import pytest
from fastapi import HTTPException

import models
from database import Base

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRACION = os.path.join(RAIZ, "alembic", "versions", "d4e5f6a7b8c9_add_teams.py")


@pytest.fixture(scope="module")
def tabla():
    return Base.metadata.tables["teams"]


# --------------------------------------------------------------------------- #
# El modelo
# --------------------------------------------------------------------------- #


def test_la_tabla_equipos_esta_registrada():
    assert "teams" in Base.metadata.tables


def test_los_tres_miembros_son_obligatorios(tabla):
    """Un equipo no puede estar incompleto, y lo garantiza la base.

    No es una validación de formulario: una importación de Excel, un script o una
    consola no pasan por el formulario.
    """
    for miembro in ("commercial", "designer", "technical_advisor"):
        columna = tabla.columns[miembro]
        assert not columna.nullable, f"{miembro} acepta nulos"
        assert columna.type.python_type is str


def test_una_persona_puede_integrar_varios_equipos(tabla):
    """Ningún miembro lleva unicidad: sólo el nombre del equipo.

    Un `unique` en `commercial` parecería razonable y le quitaría a la empresa la
    posibilidad de tener a la misma persona en dos zonas, dos turnos o dos
    cadenas.
    """
    for miembro in ("commercial", "designer", "technical_advisor"):
        columna = tabla.columns[miembro]
        assert not columna.unique, f"{miembro} quedó con unique"

    unicos = {c.name for c in tabla.columns if c.unique}
    assert unicos == {"name"}, f"columnas únicas inesperadas: {unicos}"

    for indice in tabla.indexes:
        if indice.unique:
            assert set(indice.columns.keys()) == {"name"}, (
                f"el índice único {indice.name} cubre {list(indice.columns.keys())}"
            )


def test_el_nombre_del_equipo_es_obligatorio_y_unico(tabla):
    nombre = tabla.columns["name"]
    assert not nombre.nullable
    assert nombre.unique


def test_el_equipo_tiene_la_familia_de_baja_logica(tabla):
    """Se da de baja como todo lo demás, no se borra."""
    for columna in ("is_active", "inactivation_reason",
                    "inactivated_by_id", "inactivated_at"):
        assert columna in tabla.columns, f"falta {columna}"


def test_los_miembros_se_normalizan_como_los_catalogos():
    """Si no, un equipo con «Pérez » y un filtro por «PÉREZ» no se encuentran."""
    equipo = models.Team(name="  equipo norte  ", commercial=" pérez ",
                         designer="gómez", technical_advisor=" lópez ")
    assert equipo.name == "EQUIPO NORTE"
    assert equipo.commercial == "PÉREZ"
    assert equipo.designer == "GÓMEZ"
    assert equipo.technical_advisor == "LÓPEZ"


# --------------------------------------------------------------------------- #
# Las columnas que hacen posible la asignación
# --------------------------------------------------------------------------- #


def test_el_cliente_puede_referenciar_un_equipo():
    columna = Base.metadata.tables["customers"].columns["team_id"]
    assert columna.nullable, "un cliente sin equipo tiene que poder existir"
    destinos = {fk.target_fullname for fk in columna.foreign_keys}
    assert destinos == {"teams.id"}, f"apunta a {destinos}"


def test_las_tres_columnas_del_cliente_siguen_existiendo():
    """No se reemplazan por el equipo: son la foto que leen los 208 usos.

    Si alguien las borrara al adoptar equipos, se romperían el listado, los
    filtros, los KPIs, los reportes y la importación de una sola vez.
    """
    columnas = Base.metadata.tables["customers"].columns
    for columna in ("assigned_commercial", "designer", "technical_advisor"):
        assert columna in columnas, f"desapareció customers.{columna}"


def test_la_asignacion_at_sabe_de_que_planta_es():
    """Sin esto, dos plantas con AT distinto no se pueden representar."""
    columna = Base.metadata.tables["at_assignments"].columns["plant"]
    assert columna.nullable, "una asignación vieja sin planta tiene que poder leerse"


def test_hay_indice_por_cliente_y_planta():
    indices = {i.name for i in Base.metadata.tables["at_assignments"].indexes}
    assert "ix_at_assignments_customer_plant" in indices


# --------------------------------------------------------------------------- #
# La migración y el modelo tienen que decir lo mismo
# --------------------------------------------------------------------------- #


def _columnas_de_la_migracion() -> set:
    """Las columnas que la migración crea para `teams`, leídas del código."""
    arbol = ast.parse(open(MIGRACION, encoding="utf-8").read())
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        funcion = nodo.func
        if not (isinstance(funcion, ast.Attribute) and funcion.attr == "create_table"):
            continue
        if not nodo.args or not isinstance(nodo.args[0], ast.Constant):
            continue
        if nodo.args[0].value != "teams":
            continue
        nombres = set()
        for argumento in nodo.args[1:]:
            if (isinstance(argumento, ast.Call)
                    and isinstance(argumento.func, ast.Attribute)
                    and argumento.func.attr == "Column"
                    and argumento.args
                    and isinstance(argumento.args[0], ast.Constant)):
                nombres.add(argumento.args[0].value)
        return nombres
    raise AssertionError("la migración no crea la tabla `teams`")


def test_la_migracion_crea_todas_las_columnas_del_modelo(tabla):
    """Una columna en el modelo y no en la migración es una base que no arranca."""
    del_modelo = set(tabla.columns.keys())
    de_la_migracion = _columnas_de_la_migracion()

    faltan = sorted(del_modelo - de_la_migracion)
    sobran = sorted(de_la_migracion - del_modelo)

    assert not faltan, f"columnas del modelo ausentes en la migración: {faltan}"
    assert not sobran, f"columnas en la migración que el modelo no declara: {sobran}"


def _columnas_agregadas() -> dict:
    """Pares (tabla, columna) de los `op.add_column` de la migración."""
    arbol = ast.parse(open(MIGRACION, encoding="utf-8").read())
    agregadas = {}
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        funcion = nodo.func
        if not (isinstance(funcion, ast.Attribute) and funcion.attr == "add_column"):
            continue
        if len(nodo.args) < 2:
            continue
        tabla, columna = nodo.args[0], nodo.args[1]
        if not (isinstance(tabla, ast.Constant) and isinstance(columna, ast.Call)):
            continue
        if not (isinstance(columna.func, ast.Attribute)
                and columna.func.attr == "Column" and columna.args):
            continue
        nombre = columna.args[0]
        if isinstance(nombre, ast.Constant):
            agregadas[(tabla.value, nombre.value)] = columna
    return agregadas


def test_la_migracion_agrega_team_id_y_plant():
    agregadas = _columnas_agregadas()
    assert ("customers", "team_id") in agregadas, "falta customers.team_id"
    assert ("at_assignments", "plant") in agregadas, "falta at_assignments.plant"
    # Y ninguna otra: una columna de más en la migración es deriva silenciosa.
    assert set(agregadas) == {("customers", "team_id"), ("at_assignments", "plant")}


def test_las_columnas_agregadas_son_nullable():
    """Los clientes y las asignaciones que ya existen no tienen equipo ni planta."""
    for (tabla, columna), llamada in _columnas_agregadas().items():
        nullable = [
            k.value.value for k in llamada.keywords
            if k.arg == "nullable" and isinstance(k.value, ast.Constant)
        ]
        assert nullable == [True], f"{tabla}.{columna} no quedó nullable"


def test_la_migracion_tiene_vuelta_atras():
    """Sin `downgrade` no hay forma de revertir un despliegue que salió mal."""
    fuente = open(MIGRACION, encoding="utf-8").read()
    arbol = ast.parse(fuente)
    funciones = {n.name for n in arbol.body if isinstance(n, ast.FunctionDef)}
    assert {"upgrade", "downgrade"} <= funciones

    cuerpo = fuente.split("def downgrade")[1]
    assert "drop_table" in cuerpo
    assert "drop_column" in cuerpo


def test_la_cadena_de_migraciones_tiene_una_sola_cabeza():
    """Dos cabezas dejan la base en un estado que depende de cuál corras."""
    revisiones, bajadas = {}, set()
    for archivo in glob.glob(os.path.join(RAIZ, "alembic", "versions", "*.py")):
        texto = open(archivo, encoding="utf-8").read()
        # Conviven dos formatos: `revision = "x"` y el que genera Alembic,
        # `revision: str = 'x'` con `down_revision: Union[str, Sequence[str],
        # None] = 'y'`. El patrón viejo sólo entendía el primero, así que las
        # revisiones del segundo formato aparecían como «inexistentes».
        rev = re.search(r"^revision\s*(?::[^=]+)?=\s*[\"']([^\"']+)", texto, re.M)
        down = re.search(r"^down_revision\s*(?::[^=]+)?=\s*[\"']([^\"']+)",
                         texto, re.M)
        if rev:
            revisiones[rev.group(1)] = os.path.basename(archivo)
            if down:
                bajadas.add(down.group(1))

    cabezas = sorted(r for r in revisiones if r not in bajadas)
    assert len(cabezas) == 1, f"se esperaba una sola cabeza: {cabezas}"

    # Y que ninguna migración apunte a una revisión que no existe: una bajada
    # colgada deja `alembic upgrade head` sin saber por dónde seguir.
    huerfanas = sorted(b for b in bajadas if b not in revisiones)
    assert not huerfanas, f"hay migraciones que apuntan a una revisión inexistente: {huerfanas}"


# --------------------------------------------------------------------------- #
# El servicio: validación sin base
# --------------------------------------------------------------------------- #


def test_un_equipo_incompleto_se_rechaza_con_un_mensaje():
    """El `NOT NULL` es la garantía; esto es la explicación.

    Sin esta validación, un equipo incompleto llegaría al `INSERT` y el usuario
    vería un error 500 en vez de saber qué campo le falta.
    """
    from services import team_service

    for campo, etiqueta in (("commercial", "comercial"), ("designer", "diseñador"),
                            ("technical_advisor", "AT")):
        valores = {"name": "EQUIPO X", "commercial": "A", "designer": "B",
                   "technical_advisor": "C"}
        valores[campo] = "   "
        with pytest.raises(HTTPException) as exc:
            team_service._validar(valores["name"], valores["commercial"],
                                  valores["designer"], valores["technical_advisor"])
        assert exc.value.status_code == 400
        assert etiqueta in exc.value.detail, exc.value.detail


def test_un_equipo_sin_nombre_se_rechaza():
    from services import team_service

    with pytest.raises(HTTPException) as exc:
        team_service._validar("", "A", "B", "C")
    assert "nombre" in exc.value.detail.lower()


def test_los_miembros_se_normalizan_al_validar():
    from services import team_service

    valores = team_service._validar("  norte  ", " pérez ", "gómez", " lópez ")
    assert valores == {"name": "NORTE", "commercial": "PÉREZ",
                       "designer": "GÓMEZ", "technical_advisor": "LÓPEZ"}


# --------------------------------------------------------------------------- #
# Las rutas y las plantillas, sin base
# --------------------------------------------------------------------------- #


def test_las_rutas_de_equipos_estan_registradas():
    import main

    rutas = {(sorted(r.methods)[0], r.path) for r in main.app.routes
             if getattr(r, "path", "").startswith("/equipos")}
    assert rutas == {
        ("GET", "/equipos"),
        ("POST", "/equipos/nuevo"),
        ("GET", "/equipos/{team_id}/editar"),
        ("POST", "/equipos/{team_id}/editar"),
        ("POST", "/equipos/{team_id}/desactivar"),
        ("POST", "/equipos/{team_id}/actualizar-asignaciones"),
        ("POST", "/equipos/{team_id}/reactivar"),
    }


def test_la_pantalla_de_equipos_esta_en_el_menu():
    """El menú ya no está escrito a mano: se arma desde el catálogo de módulos.

    Antes esta prueba miraba `layout.html` buscando el `href`. Ahora el enlace sale
    de `services/permisos.py`, así que se comprueba ahí y que la plantilla lo
    recorra.
    """
    from services import permisos

    modulo = permisos.modulo_por_clave("equipos")
    assert modulo is not None, "Equipos no está en el catálogo de módulos"
    assert modulo.ruta == "/equipos"
    assert modulo.grupo == "Operaciones"

    # Y el menú de alguien que lo tiene lo incluye.
    usuario = type("_U", (), {"role": "user", "modulos": ["equipos"]})()
    en_menu = [m.clave for g in permisos.menu(usuario) for m in g["modulos"]]
    assert "equipos" in en_menu

    layout = open(os.path.join(RAIZ, "templates", "layout.html"), encoding="utf-8").read()
    assert "menu_lateral(request)" in layout, "el layout no arma el menú del catálogo"


def test_los_formularios_de_equipos_mandan_el_csrf():
    """Van como formulario, así el middleware los valida. Sin el campo, no pasan."""
    for nombre in ("equipos.html", "editar_equipo.html"):
        fuente = open(os.path.join(RAIZ, "templates", nombre), encoding="utf-8").read()
        assert 'name="csrf_token"' in fuente, nombre


def test_las_plantillas_usan_el_modal_del_componente():
    """`test_ui.py` prohíbe los modales escritos a mano; acá se ve el porqué."""
    fuente = open(os.path.join(RAIZ, "templates", "equipos.html"), encoding="utf-8").read()
    assert "import modal" in fuente
    assert 'role="dialog"' not in fuente


def test_la_pantalla_avisa_que_editar_no_toca_a_los_clientes():
    """Es lo que más se puede malinterpretar de todo el cambio."""
    fuente = open(os.path.join(RAIZ, "templates", "editar_equipo.html"),
                  encoding="utf-8").read()
    assert "no se aplican a los clientes" in fuente.lower()


def test_el_listado_muestra_la_advertencia_de_equipos_repetidos():
    fuente = open(os.path.join(RAIZ, "templates", "equipos.html"), encoding="utf-8").read()
    assert "repetidos" in fuente
    assert "repetido" in fuente


# --------------------------------------------------------------------------- #
# Con base de datos
# --------------------------------------------------------------------------- #


def _hay_base() -> bool:
    """¿Se puede hablar con PostgreSQL? Sin base, estas pruebas se saltean."""
    try:
        from sqlalchemy import text
        from database import engine
        with engine.connect() as conexion:
            conexion.execute(text("select 1"))
        return True
    except Exception:
        return False


requiere_base = pytest.mark.skipif(
    not _hay_base(), reason="requiere PostgreSQL: corré la suite completa")


@requiere_base
def test_crear_un_equipo_lo_guarda_completo(db_session):
    from services import team_service

    equipo = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    assert equipo.id
    assert equipo.name == "EQUIPO NORTE"
    assert equipo.commercial == "PÉREZ"
    assert equipo.is_active is True


@requiere_base
def test_no_se_pueden_crear_dos_equipos_con_el_mismo_nombre(db_session):
    from services import team_service

    team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    with pytest.raises(HTTPException) as exc:
        team_service.crear(db_session, "equipo norte", "Otro", "Otro2", "Otro3")
    # El índice único alcanza a los desactivados: el mensaje tiene que decirlo.
    assert "reactivalo" in exc.value.detail


@requiere_base
def test_editar_un_equipo_no_toca_a_los_clientes(db_session):
    """La foto del momento: es la decisión central del diseño."""
    from services import team_service
    from enums import CustomerStatus

    equipo = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    cliente = models.Customer(
        name="CARTOCOR", plant="Planta Norte",
        assigned_commercial=equipo.commercial, designer=equipo.designer,
        technical_advisor=equipo.technical_advisor, team_id=equipo.id,
        status=CustomerStatus.CLIENTE.value, is_active=True)
    db_session.add(cliente)
    db_session.commit()

    team_service.actualizar(db_session, equipo.id, "Equipo Norte", "NUEVO",
                            "Gómez", "López")
    db_session.refresh(cliente)

    assert cliente.assigned_commercial == "PÉREZ", "editar el equipo reescribió al cliente"
    assert cliente.team_id == equipo.id


@requiere_base
def test_se_cuentan_los_clientes_de_cada_equipo(db_session):
    from services import team_service
    from enums import CustomerStatus

    uno = team_service.crear(db_session, "Uno", "A", "B", "C")
    dos = team_service.crear(db_session, "Dos", "D", "E", "F")
    for planta in ("Norte", "Sur"):
        db_session.add(models.Customer(
            name="CARTOCOR", plant=planta, team_id=uno.id,
            status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.add(models.Customer(
        name="OTRO", plant="Centro", team_id=dos.id,
        status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.commit()

    assert team_service.clientes_asignados(db_session, uno.id) == 2
    assert team_service.conteo_por_equipo(db_session) == {uno.id: 2, dos.id: 1}


@requiere_base
def test_se_detectan_los_equipos_con_los_mismos_miembros(db_session):
    """No se impide, se avisa: pueden tener sentido por zona o por turno."""
    from services import team_service

    uno = team_service.crear(db_session, "Norte", "A", "B", "C")
    dos = team_service.crear(db_session, "Sur", "A", "B", "C")
    tres = team_service.crear(db_session, "Centro", "X", "Y", "Z")

    repetidos = team_service.equipos_repetidos(db_session)
    assert repetidos == {uno.id, dos.id}
    assert tres.id not in repetidos


@requiere_base
def test_la_pantalla_de_equipos_responde(client, admin_cookie):
    respuesta = client.get("/equipos", cookies={"session": admin_cookie.split("=", 1)[1]})
    assert respuesta.status_code == 200
    assert "Equipos" in respuesta.text


@requiere_base
def _csrf_de(client, cookie):
    """El token CSRF tal como lo toma el navegador: del meta del layout."""
    html = client.get("/equipos", cookies={"session": cookie.split("=", 1)[1]}).text
    coincidencia = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert coincidencia, "el layout no publicó el token CSRF"
    return coincidencia.group(1)


@requiere_base
def test_desactivar_sin_motivo_no_pasa(client, admin_cookie, db_session):
    from services import team_service

    equipo = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    cookie = admin_cookie.split("=", 1)[1]

    respuesta = client.post(
        f"/equipos/{equipo.id}/desactivar",
        data={"reason": "   ", "csrf_token": _csrf_de(client, admin_cookie)},
        cookies={"session": cookie},
        follow_redirects=False,
    )

    db_session.refresh(equipo)
    assert equipo.is_active is True, "se desactivó con el motivo vacío"
    assert respuesta.status_code == 400


@requiere_base
def test_desactivar_con_motivo_lo_deja_inactivo(client, admin_cookie, db_session):
    from services import team_service

    equipo = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    cookie = admin_cookie.split("=", 1)[1]

    respuesta = client.post(
        f"/equipos/{equipo.id}/desactivar",
        data={"reason": "Se disolvió el equipo", "csrf_token": _csrf_de(client, admin_cookie)},
        cookies={"session": cookie},
        follow_redirects=False,
    )

    db_session.refresh(equipo)
    assert respuesta.status_code == 303
    assert equipo.is_active is False
    assert equipo.inactivation_reason == "Se disolvió el equipo"


@requiere_base
def test_sin_csrf_no_se_desactiva(client, admin_cookie, db_session):
    """El middleware falla cerrada: sin token válido, la acción no ocurre.

    La respuesta es un 303 al login y no un 403 porque `/equipos/...` no empieza
    con `/api/`. Lo que importa es que el equipo siga activo.
    """
    from services import team_service

    equipo = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    cookie = admin_cookie.split("=", 1)[1]

    respuesta = client.post(
        f"/equipos/{equipo.id}/desactivar",
        data={"reason": "sin token"},
        cookies={"session": cookie},
        follow_redirects=False,
    )

    db_session.refresh(equipo)
    assert equipo.is_active is True
    assert respuesta.status_code == 303


# --------------------------------------------------------------------------- #
# Fase 3: el equipo en el alta de cliente
# --------------------------------------------------------------------------- #


def test_el_alta_de_cliente_ofrece_un_equipo():
    """Los tres desplegables sueltos ya no están: se elige un equipo."""
    fuente = open(os.path.join(RAIZ, "templates", "nuevo_cliente.html"),
                  encoding="utf-8").read()
    assert 'name="team_id"' in fuente, "el alta no ofrece equipos"
    for campo in ('name="assigned_commercial"', 'name="technical_advisor"',
                  'name="designer"'):
        assert campo not in fuente, f"sigue el desplegable suelto {campo}"


def test_el_modal_de_edicion_tambien_ofrece_un_equipo():
    fuente = open(os.path.join(RAIZ, "templates", "_cliente_form_fields.html"),
                  encoding="utf-8").read()
    assert 'name="team_id"' in fuente
    for campo in ('name="assigned_commercial"', 'name="technical_advisor"',
                  'name="designer"'):
        assert campo not in fuente, f"sigue el desplegable suelto {campo}"


def test_el_formulario_muestra_los_integrantes_del_equipo():
    """Ver a quién se le asigna la cuenta antes de guardar es el punto del cambio."""
    for nombre in ("nuevo_cliente.html", "_cliente_form_fields.html"):
        fuente = open(os.path.join(RAIZ, "templates", nombre), encoding="utf-8").read()
        assert "data-miembro=" in fuente, nombre
        assert "equipo-integrantes" in fuente, nombre


def test_el_alta_avisa_cuando_no_hay_equipos():
    """Sin equipos no se puede dar de alta un cliente, y hay que decirlo."""
    fuente = open(os.path.join(RAIZ, "templates", "nuevo_cliente.html"),
                  encoding="utf-8").read()
    assert "Todavía no hay equipos" in fuente
    assert 'href="/equipos"' in fuente


def test_el_js_del_equipo_esta_fuera_del_parcial():
    """El parcial se inserta con `innerHTML`, y así los `<script>` no se ejecutan."""
    parcial = open(os.path.join(RAIZ, "templates", "_cliente_form_fields.html"),
                   encoding="utf-8").read()
    assert "<script" not in parcial, "el parcial trae un script que nunca va a correr"

    clientes = open(os.path.join(RAIZ, "templates", "clientes.html"),
                    encoding="utf-8").read()
    assert "data-equipo-selector" in clientes


# --------------------------------------------------------------------------- #
# Fase 3: la resolución del equipo, con base
# --------------------------------------------------------------------------- #


@requiere_base
def test_un_cliente_sin_equipo_no_se_puede_crear(client, db_session, admin_cookie):
    from routers.customers import _equipo_para_asignar

    with pytest.raises(HTTPException) as exc:
        _equipo_para_asignar(db_session, None)
    assert "equipo" in exc.value.detail.lower()


@requiere_base
def test_un_equipo_inexistente_o_inactivo_se_rechaza(db_session):
    from routers.customers import _equipo_para_asignar
    from services import team_service

    with pytest.raises(HTTPException):
        _equipo_para_asignar(db_session, 999999)

    equipo = team_service.crear(db_session, "Apagado", "A", "B", "C")
    equipo.is_active = False
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        _equipo_para_asignar(db_session, equipo.id)
    assert "desactivado" in exc.value.detail.lower()


@requiere_base
def test_el_alta_copia_los_miembros_del_equipo(db_session):
    """Las tres columnas del cliente se llenan desde el equipo, no a mano."""
    from services import customer_service, team_service

    equipo = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    creado = customer_service.create_customer(
        db_session, "CARTOCOR", "Planta Norte", "Metalurgia",
        equipo.commercial, equipo.technical_advisor, equipo.designer,
        "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
        team_id=equipo.id)

    assert creado.team_id == equipo.id
    assert creado.assigned_commercial == equipo.commercial
    assert creado.designer == equipo.designer
    assert creado.technical_advisor == equipo.technical_advisor


@requiere_base
def test_la_asignacion_at_queda_con_la_planta(db_session):
    """Una asignación por planta: es lo que hace posible un AT por planta."""
    from services import customer_service, team_service

    equipo = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    customer_service.create_customer(
        db_session, "CARTOCOR", "Planta Norte", "Metalurgia",
        equipo.commercial, equipo.technical_advisor, equipo.designer,
        "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
        team_id=equipo.id)

    asignacion = db_session.query(models.ATAssignment).filter_by(
        customer_name="CARTOCOR").one()
    assert asignacion.plant == "Planta Norte"
    assert asignacion.technical_advisor == equipo.technical_advisor


@requiere_base
def test_cambiar_el_equipo_de_una_planta_no_toca_a_las_otras(db_session):
    """El caso que motivó todo: un cliente con varias plantas y equipos distintos.

    Antes, cambiar el AT de una planta reescribía el de todas, porque la
    asignación se buscaba sólo por nombre de cliente.
    """
    from services import customer_service, team_service

    norte = team_service.crear(db_session, "Norte", "Pérez", "Gómez", "López")
    sur = team_service.crear(db_session, "Sur", "Otro", "Otro2", "Otro3")
    centro = team_service.crear(db_session, "Centro", "Tercero", "Tercero2", "Tercero3")

    def alta(planta, equipo):
        return customer_service.create_customer(
            db_session, "CARTOCOR", planta, "Metalurgia",
            equipo.commercial, equipo.technical_advisor, equipo.designer,
            "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
            team_id=equipo.id)

    alta("Planta Norte", norte)
    alta("Planta Sur", sur)

    plantas = {c.plant: c for c in db_session.query(models.Customer).all()}

    # Se cambia **sólo** la planta Norte, a un tercer equipo.
    customer_service.update_customer(
        db_session, plantas["Planta Norte"].id, "CARTOCOR", "Planta Norte",
        "Metalurgia", centro.commercial, centro.technical_advisor, centro.designer,
        "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
        team_id=centro.id)

    db_session.expire_all()
    plantas = {c.plant: c for c in db_session.query(models.Customer).all()}

    assert plantas["Planta Norte"].team_id == centro.id
    assert plantas["Planta Norte"].assigned_commercial == centro.commercial

    # La planta Sur quedó intacta: ni el equipo ni los nombres cambiaron.
    assert plantas["Planta Sur"].team_id == sur.id
    assert plantas["Planta Sur"].assigned_commercial == sur.commercial
    assert plantas["Planta Sur"].technical_advisor == sur.technical_advisor


@requiere_base
def test_el_alta_lista_los_equipos_cuando_hay(client, db_session, admin_cookie):
    """La otra rama: con equipos cargados, el selector aparece y los ofrece.

    En producción hoy no se puede comprobar porque los catálogos de personas
    están vacíos y todavía no hay ningún equipo: la pantalla muestra el aviso.
    """
    from services import team_service

    team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    cookie = admin_cookie.split("=", 1)[1]

    r = client.get("/nuevo-cliente", cookies={"session": cookie})
    assert r.status_code == 200
    assert 'name="team_id"' in r.text, "con equipos, el selector tiene que estar"
    # El nombre se guarda en mayúsculas, como los catálogos.
    assert "EQUIPO NORTE" in r.text, "el equipo no aparece entre las opciones"
    assert "Todavía no hay equipos" not in r.text
    assert 'name="assigned_commercial"' not in r.text


@requiere_base
def test_el_modal_de_edicion_lista_los_equipos(client, db_session, admin_cookie):
    from services import customer_service, team_service
    from enums import CustomerStatus

    norte = team_service.crear(db_session, "Equipo Norte", "Pérez", "Gómez", "López")
    cliente = models.Customer(
        name="CARTOCOR", plant="Planta Norte",
        assigned_commercial=norte.commercial, designer=norte.designer,
        technical_advisor=norte.technical_advisor, team_id=norte.id,
        status=CustomerStatus.CLIENTE.value, is_active=True)
    db_session.add(cliente)
    db_session.commit()

    cookie = admin_cookie.split("=", 1)[1]
    r = client.get(f"/editar-cliente/{cliente.id}",
                   headers={"X-Requested-With": "XMLHttpRequest"},
                   cookies={"session": cookie})

    assert r.status_code == 200
    assert 'name="team_id"' in r.text
    assert "EQUIPO NORTE" in r.text
    # El equipo asignado viene preseleccionado.
    assert f'value="{norte.id}"' in r.text
    assert 'name="assigned_commercial"' not in r.text


# --------------------------------------------------------------------------- #
# Fase 4: la asignación AT por planta
# --------------------------------------------------------------------------- #


def test_la_clave_de_fila_incluye_la_planta():
    """Antes era sólo el nombre, y un cliente con tres plantas mostraba una fila."""
    from routers.control_at import _clave_fila

    class _Fila:
        def __init__(self, name, plant):
            self.name, self.plant = name, plant

    assert _clave_fila(_Fila("CARTOCOR", "Norte")) != _clave_fila(_Fila("CARTOCOR", "Sur"))
    assert _clave_fila(_Fila("CARTOCOR", "Norte")) == _clave_fila(_Fila("CARTOCOR", "Norte"))
    # Sin planta se usa cadena vacía, para poder comparar con None.
    assert _clave_fila(_Fila("CARTOCOR", None)) == ("CARTOCOR", "")


def test_el_formulario_de_asignacion_pide_la_planta():
    fuente = open(os.path.join(RAIZ, "templates", "control_at.html"),
                  encoding="utf-8").read()
    assert 'id="modal-plant"' in fuente
    assert "cargarPlantas" in fuente
    assert "plant: planta" in fuente


@requiere_base
def test_una_asignacion_necesita_planta(db_session):
    """Es de una planta, no del cliente entero."""
    from services import kpi_service

    with pytest.raises(HTTPException) as exc:
        kpi_service.quick_create_assignment(db_session, "CARTOCOR", at="LÓPEZ")
    assert "planta" in exc.value.detail.lower()


@requiere_base
def test_un_cliente_puede_tener_una_asignacion_por_planta(db_session):
    """El caso que antes era imposible: rechazaba la segunda por repetir el nombre."""
    from services import kpi_service

    norte = kpi_service.quick_create_assignment(db_session, "CARTOCOR", at="LÓPEZ",
                                                plant="Planta Norte")
    sur = kpi_service.quick_create_assignment(db_session, "CARTOCOR", at="GÓMEZ",
                                              plant="Planta Sur")

    assert norte.plant == "Planta Norte"
    assert sur.plant == "Planta Sur"
    assert norte.id != sur.id


@requiere_base
def test_no_se_repiten_asignaciones_en_la_misma_planta(db_session):
    from services import kpi_service

    kpi_service.quick_create_assignment(db_session, "CARTOCOR", at="LÓPEZ",
                                        plant="Planta Norte")
    with pytest.raises(HTTPException) as exc:
        kpi_service.quick_create_assignment(db_session, "CARTOCOR", at="GÓMEZ",
                                            plant="Planta Norte")
    assert "Planta Norte" in exc.value.detail


@requiere_base
def test_control_at_muestra_una_fila_por_planta(client, db_session, admin_cookie):
    """Lo que se veía mal: una sola fila por cliente, con la planta del desempate."""
    from services import kpi_service
    from enums import CustomerStatus

    # El listado parte de los clientes: cada planta es una fila de cliente.
    for planta in ("Planta Norte", "Planta Sur"):
        db_session.add(models.Customer(
            name="CARTOCOR", plant=planta, team_id=None,
            status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.commit()

    kpi_service.quick_create_assignment(db_session, "CARTOCOR", at="LÓPEZ",
                                        plant="Planta Norte")
    kpi_service.quick_create_assignment(db_session, "CARTOCOR", at="GÓMEZ",
                                        plant="Planta Sur")

    cookie = admin_cookie.split("=", 1)[1]
    html = client.get("/control-at", cookies={"session": cookie}).text

    assert "Planta Norte" in html
    assert "Planta Sur" in html
    # Los dos AT aparecen: antes uno solo ganaba el desempate.
    assert "LÓPEZ" in html
    assert "GÓMEZ" in html


@requiere_base
def test_el_total_no_cuenta_las_versiones_historicas(db_session):
    """Paginar con el número inflado mostraba páginas incompletas."""
    from routers.control_at import _control_at_query, _total_filas
    from services import kpi_service
    from enums import CustomerStatus

    db_session.add(models.Customer(
        name="CARTOCOR", plant="Planta Norte", team_id=None,
        status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.commit()

    # Tres versiones de la misma asignación: dos cerradas y una vigente.
    for i in range(3):
        db_session.add(models.ATAssignment(
            customer_name="CARTOCOR", plant="Planta Norte",
            technical_advisor=f"AT {i}",
            valid_from=datetime.datetime(2026, 1, 1) + datetime.timedelta(days=i),
            valid_to=None if i == 2 else datetime.datetime(2026, 2, 1)))
    db_session.commit()

    assert _total_filas(_control_at_query(db_session, vigentes=False)) == 1


# --------------------------------------------------------------------------- #
# Fase 6: propagar el equipo a sus clientes
# --------------------------------------------------------------------------- #


def test_la_pantalla_de_equipos_ofrece_actualizar_asignaciones():
    fuente = open(os.path.join(RAIZ, "templates", "equipos.html"),
                  encoding="utf-8").read()
    assert "data-actualizar-equipo" in fuente
    assert "/actualizar-asignaciones" in fuente
    # Y explica por qué no se hace solo.
    assert "no</strong> cambia a sus clientes" in fuente or "no cambia a sus clientes" in fuente


def test_el_formulario_de_cliente_ofrece_aplicar_a_todas_las_plantas():
    fuente = open(os.path.join(RAIZ, "templates", "_cliente_form_fields.html"),
                  encoding="utf-8").read()
    assert 'name="aplicar_a_todas"' in fuente
    # Sin marcar, sólo cambia la planta editada.
    assert "Sólo cambia la planta" in fuente or "sólo cambia la planta" in fuente


@requiere_base
def test_actualizar_asignaciones_reescribe_los_clientes(db_session):
    """El caso opuesto al diseño: acá sí se quiere que los clientes cambien."""
    from services import customer_service, team_service

    equipo = team_service.crear(db_session, "Norte", "Pérez", "Gómez", "López")
    cliente = customer_service.create_customer(
        db_session, "CARTOCOR", "Planta 1", "Metalurgia",
        equipo.commercial, equipo.technical_advisor, equipo.designer,
        "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
        team_id=equipo.id)

    # El equipo cambia de AT.
    team_service.actualizar(db_session, equipo.id,
                            equipo.name,              # nombre
                            equipo.commercial,        # comercial
                            equipo.designer,          # diseñador
                            "NUEVO AT")               # AT

    # Editar el equipo **no** tocó al cliente.
    db_session.expire_all()
    assert customer_service.get_customer(db_session, cliente.id).technical_advisor == "LÓPEZ"

    # Actualizar las asignaciones sí.
    resultado = team_service.actualizar_asignaciones(db_session, equipo.id)
    assert resultado["clientes"] == 1

    db_session.expire_all()
    actualizado = customer_service.get_customer(db_session, cliente.id)
    assert actualizado.technical_advisor == "NUEVO AT"
    assert actualizado.team_id == equipo.id


@requiere_base
def test_actualizar_asignaciones_mueve_la_asignacion_at(db_session):
    """Si no, la ficha diría un AT y el control de asignaciones otro."""
    from services import customer_service, kpi_service, team_service

    equipo = team_service.crear(db_session, "Norte", "Pérez", "Gómez", "López")
    customer_service.create_customer(
        db_session, "CARTOCOR", "Planta 1", "Metalurgia",
        equipo.commercial, equipo.technical_advisor, equipo.designer,
        "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
        team_id=equipo.id)

    team_service.actualizar(db_session, equipo.id,
                            equipo.name,              # nombre
                            equipo.commercial,        # comercial
                            equipo.designer,          # diseñador
                            "NUEVO AT")               # AT
    team_service.actualizar_asignaciones(db_session, equipo.id)

    asignacion = db_session.query(models.ATAssignment).filter_by(
        customer_name="CARTOCOR", plant="Planta 1").one()
    assert asignacion.technical_advisor == "NUEVO AT"


@requiere_base
def test_aplicar_a_todas_las_plantas_alcanza_a_las_hermanas(db_session):
    from services import customer_service, team_service
    from enums import CustomerStatus

    norte = team_service.crear(db_session, "Norte", "Pérez", "Gómez", "López")
    sur = team_service.crear(db_session, "Sur", "Otro", "Otro2", "Otro3")

    filas = []
    for planta in ("Planta 1", "Planta 2", "Planta 3"):
        filas.append(models.Customer(
            name="CARTOCOR", plant=planta, team_id=norte.id,
            assigned_commercial=norte.commercial, designer=norte.designer,
            technical_advisor=norte.technical_advisor,
            status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.add_all(filas)
    # Otro cliente con el mismo equipo: no se tiene que tocar.
    db_session.add(models.Customer(
        name="OTRO CLIENTE", plant="Planta 1", team_id=norte.id,
        status=CustomerStatus.CLIENTE.value, is_active=True))
    db_session.commit()

    cambiadas = team_service.aplicar_a_todas_las_plantas(
        db_session, sur.id, "CARTOCOR", filas[0].id)

    assert cambiadas == 2, "tienen que ser las otras dos plantas, no la editada"

    db_session.expire_all()
    por_planta = {c.plant: c for c in db_session.query(models.Customer).filter_by(
        name="CARTOCOR").all()}
    assert por_planta["Planta 1"].team_id == norte.id, "la editada no se toca"
    assert por_planta["Planta 2"].team_id == sur.id
    assert por_planta["Planta 3"].team_id == sur.id
    assert por_planta["Planta 2"].assigned_commercial == sur.commercial

    # El otro cliente con el mismo equipo queda intacto.
    otro = db_session.query(models.Customer).filter_by(name="OTRO CLIENTE").one()
    assert otro.team_id == norte.id


@requiere_base
def test_cada_planta_nueva_recibe_su_asignacion(db_session):
    """El bug que apareció recién al probar el circuito completo a mano.

    El alta buscaba la asignación existente sólo por nombre de cliente, así que la
    segunda planta encontraba la de la primera y no creaba nada: esa planta quedaba
    sin AT en Control AT. Se veía como una fila con el cliente y la planta en blanco.
    """
    from services import customer_service, team_service

    equipo = team_service.crear(db_session, "Norte", "Pérez", "Gómez", "López")

    for planta in ("Planta Norte", "Planta Sur"):
        customer_service.create_customer(
            db_session, "CARTOCOR", planta, "Metalurgia",
            equipo.commercial, equipo.technical_advisor, equipo.designer,
            "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
            team_id=equipo.id)

    asignaciones = db_session.query(models.ATAssignment).filter_by(
        customer_name="CARTOCOR").all()
    assert len(asignaciones) == 2, "cada planta necesita la suya"
    assert {a.plant for a in asignaciones} == {"Planta Norte", "Planta Sur"}
    assert all(a.technical_advisor == equipo.technical_advisor for a in asignaciones)


@requiere_base
def test_la_segunda_planta_aparece_con_su_at_en_control_at(client, db_session, admin_cookie):
    """Y en la pantalla: sin la asignación, la fila salía sin AT."""
    from services import customer_service, team_service

    equipo = team_service.crear(db_session, "Norte", "Pérez", "Gómez", "López")
    for planta in ("Planta Norte", "Planta Sur"):
        customer_service.create_customer(
            db_session, "CARTOCOR", planta, "Metalurgia",
            equipo.commercial, equipo.technical_advisor, equipo.designer,
            "Calle 1", "Rosario", "Activo", None, [], [], [], [], [], "",
            team_id=equipo.id)

    cookie = admin_cookie.split("=", 1)[1]
    html = client.get("/control-at", cookies={"session": cookie}).text
    assert "Planta Norte" in html
    assert "Planta Sur" in html
    # Las dos filas tienen que traer el AT del equipo.
    assert html.count(equipo.technical_advisor) >= 2
