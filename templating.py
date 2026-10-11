"""Single shared Jinja2 environment for the whole application.

Every router used to build its own ``Jinja2Templates`` instance (18 in total),
which meant filters and globals had to be registered 18 times — and in practice
they were not registered at all, so e.g. the ``from_json`` filter only existed
on an instance nobody used. Import ``templates`` from here instead.
"""

import glob
import hashlib
import datetime
import json
import os

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

_RAIZ = os.path.dirname(os.path.abspath(__file__))


def _huella_estaticos() -> str:
    """Huella de los estáticos, para romper la caché.

    nginx sirve /static con `Cache-Control: public, immutable` y 30 días de
    vigencia. `immutable` le dice al navegador que NO revalide: guarda el archivo
    y lo usa tal cual hasta que expire. Con una URL fija, eso significa que
    ningún cambio de CSS o JS llega al usuario hasta un mes después (o hasta que
    limpie la caché a mano).

    Por eso los estáticos se piden con `?v=<huella>`: cada build cambia la
    dirección y el navegador los vuelve a bajar. Con las URLs versionadas, el
    `immutable` pasa a ser lo correcto, porque un cambio de contenido siempre
    implica un cambio de URL.

    La huella sale de la fecha de modificación de los archivos: es barata y
    alcanza, porque cada despliegue reinicia el servicio.
    """
    partes = []
    for patron in ("static/css/*.css", "static/js/*.js", "static/img/*"):
        for ruta in sorted(glob.glob(os.path.join(_RAIZ, patron))):
            try:
                partes.append(f"{os.path.basename(ruta)}:{int(os.path.getmtime(ruta))}")
            except OSError:
                continue
    if not partes:
        return "0"
    return hashlib.sha1("|".join(partes).encode()).hexdigest()[:10]


ASSET_VERSION = _huella_estaticos()


def static_url(path: str) -> str:
    """URL de un estático con la huella que rompe la caché."""
    return f"/static/{str(path).lstrip('/')}?v={ASSET_VERSION}"


templates.env.globals["static_url"] = static_url
templates.env.globals["asset_version"] = ASSET_VERSION


def _from_json(value):
    """Decode a JSON string, tolerating already-decoded values."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _fmt_date(value, fmt: str = "%d/%m/%Y"):
    """Format a date/datetime consistently across templates.

    Las fechas llegan de tres formas: objetos date/datetime, texto ISO (columnas
    String y campos de form_data) y texto ya formateado. Sin parsear el texto, la
    tabla de visitas mostraba ``2026-09-24`` mientras el resto de la aplicación
    mostraba ``24/09/2026``.
    """
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    texto = str(value).strip()
    for patron in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(texto[:19], patron).strftime(fmt)
        except ValueError:
            continue
    return texto


def _fmt_datetime(value):
    return _fmt_date(value, "%d/%m/%Y %H:%M")


def _num(value):
    """Thousands-separated integer, falling back to the raw value."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return value


templates.env.filters["from_json"] = _from_json
templates.env.filters["fecha"] = _fmt_date
templates.env.filters["fechahora"] = _fmt_datetime
templates.env.filters["num"] = _num

__all__ = ["templates"]
