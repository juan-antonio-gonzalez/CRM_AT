"""Shared helpers for services."""

import json
from datetime import date, datetime
from typing import Any


def safe_json_loads(raw: str, default: Any = None) -> dict:
    if default is None:
        default = {}
    if not raw:
        return default
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return default
    except (json.JSONDecodeError, TypeError):
        return default


def shift_months(anchor: date, months: int) -> date:
    """Return the first day of the month ``months`` away from ``anchor``.

    Implemented with real calendar arithmetic. The dashboard used to approximate
    this with ``anchor - timedelta(days=i * 30)``, which skips and duplicates
    months: from 2026-05-15 it produced Dec, Jan, Jan, Mar, Apr, May — February
    vanished and January was counted twice.
    """
    total = (anchor.year * 12 + (anchor.month - 1)) + months
    year, month_index = divmod(total, 12)
    return date(year, month_index + 1, 1)


def month_buckets(anchor: date, count: int = 6) -> list:
    """Return the last ``count`` months ending at ``anchor``, oldest first.

    Each item is ``(key, label, first_day, last_day)`` where ``key`` is
    ``YYYY-MM`` and ``last_day`` is inclusive.
    """
    import calendar

    anchor_first = anchor.replace(day=1)
    buckets = []
    for offset in range(count - 1, -1, -1):
        first = shift_months(anchor_first, -offset)
        last = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
        buckets.append((first.strftime("%Y-%m"), first.strftime("%b %y"), first, last))
    return buckets


def parse_fecha(value) -> date | None:
    """Best-effort parse of the legacy free-text ``fecha`` columns.

    ``fecha`` is still a VARCHAR on several tables, so comparisons are done on
    parsed dates instead of lexicographically.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:len(fmt) + 4].strip(), fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def month_date_range(anio: str, mes: str) -> tuple:
    """Inclusive ISO date range for a year/month filter.

    Replaces two copy-pasted blocks that hardcoded ``last_day = 30`` and
    February to 28, which was wrong in leap years (and wrong for 31-day months
    depending on the dropdown value).
    """
    import calendar

    if not anio:
        return "", ""
    if not mes:
        return f"{anio}-01-01", f"{anio}-12-31"
    try:
        year, month = int(anio), int(mes)
    except (TypeError, ValueError):
        return "", ""
    if not 1 <= month <= 12:
        return "", ""
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def periodo_anterior(anio: str = "", mes: str = "", hoy=None) -> tuple:
    """Rango ISO y etiqueta del período anterior al que se está mirando.

    Un número sin referencia no comunica: "61 visitas" no dice nada, "61, +18%
    contra el mes pasado" sí. El período anterior depende del filtro activo, y
    cuando no hay filtro se comparan los últimos 30 días contra los 30 previos,
    que es la comparación que siempre está disponible y siempre significa lo mismo.

    Devuelve (desde, hasta, etiqueta).
    """
    import calendar
    import datetime as _dt

    hoy = hoy or _dt.date.today()

    # Con año y mes: el mes anterior.
    if anio and mes:
        try:
            y, m = int(anio), int(mes)
            m -= 1
            if m == 0:
                m, y = 12, y - 1
            ultimo = calendar.monthrange(y, m)[1]
            nombre = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                      "agosto", "septiembre", "octubre", "noviembre", "diciembre"][m - 1]
            return (f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{ultimo:02d}",
                    f"{nombre} de {y}")
        except (TypeError, ValueError):
            pass

    # Con año: el año anterior.
    if anio:
        try:
            y = int(anio) - 1
            return f"{y:04d}-01-01", f"{y:04d}-12-31", f"el año {y}"
        except (TypeError, ValueError):
            pass

    # Sin filtro: los 30 días inmediatamente anteriores a los últimos 30.
    # El `- 31` es a propósito: si terminara en `hoy - 30` habría un día contado
    # en los dos períodos, y ese día se sumaría dos veces en la comparación.
    hasta = hoy - _dt.timedelta(days=31)
    desde = hoy - _dt.timedelta(days=60)
    return desde.isoformat(), hasta.isoformat(), "los 30 días anteriores"


def ultimos_30(hoy=None) -> tuple:
    """Rango ISO de los últimos 30 días, con su etiqueta."""
    import datetime as _dt
    hoy = hoy or _dt.date.today()
    return ((hoy - _dt.timedelta(days=30)).isoformat(), hoy.isoformat(),
            "los últimos 30 días")
