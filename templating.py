"""Single shared Jinja2 environment for the whole application.

Every router used to build its own ``Jinja2Templates`` instance (18 in total),
which meant filters and globals had to be registered 18 times — and in practice
they were not registered at all, so e.g. the ``from_json`` filter only existed
on an instance nobody used. Import ``templates`` from here instead.
"""

import json

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


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
    """Format a date/datetime consistently across templates."""
    if not value:
        return ""
    try:
        return value.strftime(fmt)
    except AttributeError:
        return str(value)


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
