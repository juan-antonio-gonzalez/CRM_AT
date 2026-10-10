from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import models
from database import get_db
import datetime
from templating import templates

router = APIRouter(tags=["historial_at"])


def _today():
    return datetime.date.today().isoformat()


def _parse_dt(val):
    if not val:
        return None
    try:
        return datetime.datetime.fromisoformat(val.replace("T", " ") if "T" in val else val)
    except Exception:
        return None


def _cliente_nombre_planta(cliente_text: str) -> tuple:
    if not cliente_text:
        return "", ""
    if "(" in cliente_text:
        name = cliente_text.split("(")[0].strip()
        plant = cliente_text.split("(")[1].rstrip(")").strip()
        return name, plant
    return cliente_text, ""


@router.get("/historial-at", response_class=HTMLResponse)
async def historial_at(
    request: Request,
    desde: str = Query("", alias="desde"),
    hasta: str = Query("", alias="hasta"),
    cliente: str = Query("", alias="cliente"),
    at: str = Query("", alias="at"),
    db: Session = Depends(get_db),
):
    hasta = hasta or _today()
    desde = desde or ""
    hasta_dt = _parse_dt(hasta)
    desde_dt = _parse_dt(desde)

    # ── PERÍODOS DEL HISTORIAL ──
    hist_q = db.query(models.ATAssignment).filter(
        models.ATAssignment.valid_from <= (hasta_dt or datetime.datetime.utcnow())
    )
    if desde_dt:
        hist_q = hist_q.filter(
            (models.ATAssignment.valid_to.is_(None)) |
            (models.ATAssignment.valid_to >= desde_dt)
        )
    if cliente:
        hist_q = hist_q.filter(models.ATAssignment.customer_name.ilike(f"%{cliente}%"))
    if at:
        hist_q = hist_q.filter(models.ATAssignment.technical_advisor.ilike(f"%{at}%"))
    historial = hist_q.order_by(
        models.ATAssignment.customer_name, models.ATAssignment.valid_from.desc()
    ).all()

    # ── INDICADORES ──
    vigentes = sum(1 for h in historial if h.valid_to is None)
    cerrados = len(historial) - vigentes
    asignaciones_hist = len(historial)

    std_hist = sum(h.standard_visits or 0 for h in historial)
    prem_hist = sum(h.premium_visits or 0 for h in historial)

    por_status = {}
    por_at = {}
    por_cliente = {}
    for h in historial:
        st = h.status or "Prospecto"
        por_status[st] = por_status.get(st, 0) + 1
        if h.technical_advisor:
            por_at[h.technical_advisor] = por_at.get(h.technical_advisor, 0) + 1
        por_cliente[h.customer_name] = por_cliente.get(h.customer_name, 0) + 1

    # ── VISITAS FUERA DE CRONOGRAMA ──
    vis_q = db.query(models.TechnicalVisit2).filter(models.TechnicalVisit2.status != "Cancelado")
    if desde:
        vis_q = vis_q.filter(models.TechnicalVisit2.fecha >= desde)
    if hasta:
        vis_q = vis_q.filter(models.TechnicalVisit2.fecha <= hasta)
    visitas = vis_q.all()

    fuadera = []
    if visitas:
        customers = {(c.name, c.plant or ""): c for c in db.query(models.Customer).all()}
        # Load every assignment once instead of one SELECT per visit: this loop
        # previously issued an ATAssignment query for each row.
        assignments_by_customer = {}
        for a in db.query(models.ATAssignment).all():
            assignments_by_customer.setdefault(a.customer_name, []).append(a)

        for v in visitas:
            fd = v.form_data or {}
            nombre, planta = _cliente_nombre_planta(fd.get("cliente_nombre", ""))
            fecha_v = v.fecha or ""
            at_v = fd.get("at") or ""
            if not nombre:
                continue
            c = customers.get((nombre, planta))
            if c and c.status == "Inactivo":
                fuadera.append({"fecha": fecha_v, "cliente": nombre, "plant": planta, "at": at_v, "motivo": "Cliente inactivo"})
                continue
            fecha_v_dt = _parse_dt(fecha_v) or datetime.datetime.utcnow()
            per = None
            for candidate in assignments_by_customer.get(nombre, ()):
                starts_ok = candidate.valid_from is None or candidate.valid_from <= fecha_v_dt
                ends_ok = candidate.valid_to is None or candidate.valid_to >= fecha_v_dt
                if starts_ok and ends_ok:
                    per = candidate
                    break
            if not per:
                fuadera.append({"fecha": fecha_v, "cliente": nombre, "plant": planta, "at": at_v, "motivo": "Sin asignación vigente"})
            elif per.technical_advisor and at_v and per.technical_advisor != at_v:
                fuadera.append({"fecha": fecha_v, "cliente": nombre, "plant": planta, "at": at_v, "motivo": "AT distinto al asignado"})
    fuadera.sort(key=lambda x: x["fecha"], reverse=True)

    at_list = [
        a[0] for a in db.query(models.ATAssignment.technical_advisor)
        .distinct().order_by(models.ATAssignment.technical_advisor).all()
        if a[0]
    ]

    return templates.TemplateResponse(request, 'historial_at.html', {
        "request": request,
        "historial": historial,
        "fuadera": fuadera,
        "at_list": at_list,
        "filters": {
            "desde": desde,
            "hasta": hasta,
            "cliente": cliente,
            "at": at,
        },
        "indicadores": {
            "asignaciones": asignaciones_hist,
            "vigentes": vigentes,
            "cerrados": cerrados,
            "std": std_hist,
            "prem": prem_hist,
            "fuera_cronograma": len(fuadera),
        },
        "por_status": sorted(por_status.items(), key=lambda x: x[1], reverse=True),
        "por_at": sorted(por_at.items(), key=lambda x: x[1], reverse=True),
        "por_cliente": sorted(por_cliente.items(), key=lambda x: x[1], reverse=True),
        "active_page": "historial_at",
    })


@router.post("/historial-at/eliminar/{assignment_id}")
async def eliminar_periodo(
    assignment_id: int,
    request: Request,
    redirect: str = Query("/historial-at"),
    db: Session = Depends(get_db),
):
    db.query(models.ATAssignment).filter(models.ATAssignment.id == assignment_id).delete()
    db.commit()
    return RedirectResponse(url=redirect, status_code=303)
