"""Importación masiva desde Excel.

Cargar 200 clientes o 500 máquinas a mano es inviable. Este módulo lee una planilla,
valida cada fila y devuelve **qué se va a importar y qué no**, con el motivo. La
importación efectiva sólo ocurre después de que la persona vio la previsualización:
nunca se escribe a ciegas sobre datos reales.

El flujo es en tres pasos, y los tres pasan por acá:

    1. leer_planilla()      archivo -> filas crudas + errores de estructura
    2. validar()            filas crudas -> filas listas + errores por fila
    3. importar()           filas listas -> registros creados

Decisiones que vale la pena conocer:

* **Los encabezados se buscan por nombre, no por posición.** Se ignoran mayúsculas,
  acentos y espacios sobrantes, así "N° de Serie", "n de serie" y "Nº DE SERIE"
  encuentran la misma columna. Si alguien reordena las columnas, sigue funcionando.
* **Una fila con error no se importa, pero las demás sí.** Se informa cuáles
  quedaron afuera y por qué, en lugar de rechazar el archivo entero.
* **La validación es la misma en la previsualización y en la importación.** Si no lo
  fuera, lo que se ve en la preview no sería lo que se escribe.
"""

import io
import re
import unicodedata

import models
from enums import CustomerStatus, RelevamientoStatus


def _normalizar(texto) -> str:
    """Minúsculas, sin acentos, sin espacios sobrantes ni signos."""
    if texto is None:
        return ""
    s = str(texto).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


# ── Definición de cada planilla ──────────────────────────────────────────────
# `campo`: el atributo del modelo. `encabezado`: cómo se muestra y cómo se busca.
# `obligatorio`: si falta, la fila se rechaza con el motivo.
CLIENTES = {
    "titulo": "Clientes",
    "modelo": models.Customer,
    "columnas": [
        ("name", "Nombre", True),
        ("plant", "Planta", False),
        ("industry_sector", "Sector industrial", False),
        ("assigned_commercial", "Asesor comercial", False),
        ("technical_advisor", "Asistente técnico", False),
        ("designer", "Diseñador", False),
        ("address", "Dirección", False),
        ("city", "Ciudad", False),
        ("status", "Estado", False),
        ("observations", "Observaciones", False),
    ],
    # Cómo reconocer la misma fila ya cargada.
    "clave": "name",
    "ejemplo": ["Cartocor SA", "Planta 1", "Corrugado", "Carlos Pérez",
                "ING. GOMEZ", "Diseño", "Av. Central 123", "Rosario", "Activo",
                "Cliente histórico"],
}

MAQUINAS = {
    "titulo": "Máquinas",
    "modelo": models.Machine,
    # La primera columna es el cliente, que se resuelve por nombre a customer_id.
    "columnas": [
        ("_cliente", "Cliente", True),
        ("plant_assigned", "Planta", False),
        ("brand", "Marca", False),
        ("model", "Modelo", False),
        ("machine_type", "Tipo", False),
        ("serial_number", "Nº de serie", False),
        ("line", "Línea", False),
        ("status", "Estado", False),
    ],
    "clave": "serial_number",
    "ejemplo": ["Cartocor SA", "Planta 1", "Bobst", "Modelo 5", "Impresora",
                "SN-0001", "Línea 1", "Operativo"],
}

TIPOS = {"clientes": CLIENTES, "maquinas": MAQUINAS}


def _encabezados(hoja):
    """Primera fila no vacía, como lista de textos normalizados."""
    for fila in hoja.iter_rows(min_row=1, max_row=5, values_only=True):
        valores = [v for v in fila if v is not None and str(v).strip()]
        if valores:
            return [_normalizar(v) for v in fila], fila
    return [], ()


def leer_planilla(contenido: bytes, tipo: str):
    """Lee el archivo y devuelve (filas, error).

    `filas` es una lista de dicts con las claves de las columnas definidas. Si hay
    un problema de estructura (archivo ilegible, encabezados que no coinciden) se
    devuelve el motivo y no se sigue.
    """
    from openpyxl import load_workbook

    definicion = TIPOS.get(tipo)
    if not definicion:
        return [], f"Tipo de importación desconocido: {tipo}"

    try:
        wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception:
        return [], ("No se pudo leer el archivo. Tiene que ser una planilla de Excel "
                    "(.xlsx). Si es .xls o .csv, abrilo y guardalo como .xlsx.")

    hoja = wb.active
    encabezados, _ = _encabezados(hoja)
    if not encabezados:
        return [], "La planilla está vacía."

    # Se mapea cada columna de la planilla a un campo del modelo, buscando por
    # nombre normalizado.
    indices = {}
    for campo, etiqueta, _obligatorio in definicion["columnas"]:
        buscado = _normalizar(etiqueta)
        for i, enc in enumerate(encabezados):
            if enc == buscado:
                indices[campo] = i
                break

    obligatorios = [e for c, e, o in definicion["columnas"] if o]
    faltantes = [e for c, e, o in definicion["columnas"]
                 if o and c not in indices]
    if faltantes:
        return [], ("Faltan columnas obligatorias: " + ", ".join(faltantes) +
                    ". Descargá la plantilla para ver el formato esperado.")

    # Se leen todas las filas menos la de encabezados.
    filas = []
    fila_inicial = 2
    for numero, fila in enumerate(
            hoja.iter_rows(min_row=fila_inicial, values_only=True), start=fila_inicial):
        if fila is None or all(v is None or str(v).strip() == "" for v in fila):
            continue
        registro = {"_fila": numero}
        for campo, i in indices.items():
            valor = fila[i] if i < len(fila) else None
            registro[campo] = "" if valor is None else str(valor).strip()
        filas.append(registro)

    if not filas:
        return [], "La planilla no tiene filas de datos (sólo el encabezado)."

    return filas, None


def _validar_clientes(db, filas):
    """Valida y prepara filas de clientes."""
    existentes = {_normalizar(n) for (n,) in db.query(models.Customer.name).all()}
    vistos_en_archivo = set()
    listas, errores = [], []

    for f in filas:
        nombre = f.get("name", "").strip()
        if not nombre:
            errores.append({"fila": f["_fila"], "motivo": "Falta el nombre"})
            continue
        clave = _normalizar(nombre)
        if clave in existentes:
            errores.append({"fila": f["_fila"],
                            "motivo": f"Ya existe un cliente llamado «{nombre}»"})
            continue
        if clave in vistos_en_archivo:
            errores.append({"fila": f["_fila"],
                            "motivo": f"«{nombre}» está repetido en la planilla"})
            continue
        vistos_en_archivo.add(clave)

        estado = f.get("status", "").strip() or CustomerStatus.CLIENTE.value
        listas.append({
            "_fila": f["_fila"],
            "name": nombre,
            "plant": f.get("plant", ""),
            "industry_sector": f.get("industry_sector", ""),
            "assigned_commercial": f.get("assigned_commercial", ""),
            "technical_advisor": f.get("technical_advisor", ""),
            "designer": f.get("designer", ""),
            "address": f.get("address", ""),
            "city": f.get("city", ""),
            "status": estado,
            "relevamiento_status": RelevamientoStatus.PENDIENTE.value,
            "observations": f.get("observations", ""),
            "is_active": True,
        })
    return listas, errores


def _validar_maquinas(db, filas):
    """Valida y prepara filas de máquinas, resolviendo el cliente por nombre."""
    clientes = {_normalizar(n): i for i, n in db.query(models.Customer.id,
                                                       models.Customer.name).all()}
    series_existentes = {_normalizar(s) for (s,) in db.query(models.Machine.serial_number).all()
                         if s}
    vistos_en_archivo = set()
    listas, errores = [], []

    for f in filas:
        nombre_cliente = f.get("_cliente", "").strip()
        if not nombre_cliente:
            errores.append({"fila": f["_fila"], "motivo": "Falta el cliente"})
            continue
        cliente_id = clientes.get(_normalizar(nombre_cliente))
        if not cliente_id:
            errores.append({"fila": f["_fila"],
                            "motivo": f"No existe un cliente llamado «{nombre_cliente}». "
                                      f"Cargalo primero."})
            continue

        serie = f.get("serial_number", "").strip()
        if serie:
            clave = _normalizar(serie)
            if clave in series_existentes:
                errores.append({"fila": f["_fila"],
                                "motivo": f"Ya existe una máquina con el número de serie "
                                          f"«{serie}»"})
                continue
            if clave in vistos_en_archivo:
                errores.append({"fila": f["_fila"],
                                "motivo": f"El número de serie «{serie}» está repetido "
                                          f"en la planilla"})
                continue
            vistos_en_archivo.add(clave)

        listas.append({
            "_fila": f["_fila"],
            "customer_id": cliente_id,
            "plant_assigned": f.get("plant_assigned", ""),
            "brand": f.get("brand", ""),
            "model": f.get("model", ""),
            "machine_type": f.get("machine_type", ""),
            "serial_number": serie,
            "line": f.get("line", ""),
            "status": f.get("status", "").strip() or "Operativo",
            "relevamiento_status": RelevamientoStatus.PENDIENTE.value,
            "is_active": True,
        })
    return listas, errores


def validar(db, tipo: str, filas):
    """Devuelve (filas listas para importar, errores por fila)."""
    if tipo == "clientes":
        return _validar_clientes(db, filas)
    if tipo == "maquinas":
        return _validar_maquinas(db, filas)
    return [], [{"fila": 0, "motivo": f"Tipo desconocido: {tipo}"}]


def importar(db, tipo: str, filas):
    """Crea los registros. Se llama sólo después de la previsualización.

    Se revalida contra la base: entre la previsualización y la confirmación pudo
    cargarse algo, y no queremos duplicar.
    """
    listas, errores = validar(db, tipo, filas)
    if errores and not listas:
        return 0, len(filas), errores

    modelo = TIPOS[tipo]["modelo"]
    creados = 0
    for datos in listas:
        limpio = {k: v for k, v in datos.items() if not k.startswith("_")}
        db.add(modelo(**limpio))
        creados += 1
    db.commit()
    return creados, len(filas) - creados, errores


def plantilla(tipo: str):
    """Genera un .xlsx vacío con los encabezados correctos y una fila de ejemplo."""
    definicion = TIPOS.get(tipo)
    if not definicion:
        return None
    from services.excel import hoja_excel

    encabezados = [e for _c, e, _o in definicion["columnas"]]
    return hoja_excel(
        definicion["titulo"],
        encabezados,
        [definicion["ejemplo"]],
        f"plantilla-{tipo}.xlsx",
    )
