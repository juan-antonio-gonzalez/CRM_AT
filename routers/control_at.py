from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import models
from database import get_db
from services import pagination as pg
from services import kpi_service
from math import ceil
import datetime
from templating import templates

router = APIRouter(tags=["control_at"])


def _control_at_query(db, cliente="", at="", estandar=None, premium=None,
                      status="", vigentes=True):
    """Consulta de asignaciones AT con los filtros del listado.

    La comparten el listado y la exportación, para que exportar respete los mismos
    filtros que se ven en pantalla.
    """
    cols = [
        models.Customer.id.label("customer_id"),
        models.Customer.name,
        models.Customer.plant,
        models.ATAssignment.id.label("assignment_id"),
        models.ATAssignment.technical_advisor,
        models.ATAssignment.standard_visits,
        models.ATAssignment.premium_visits,
        models.ATAssignment.status,
        models.ATAssignment.valid_from,
        models.ATAssignment.valid_to,
    ]
    now = datetime.datetime.utcnow()
    on_condition = models.Customer.name == models.ATAssignment.customer_name
    if vigentes:
        on_condition &= or_(models.ATAssignment.valid_to.is_(None),
                            models.ATAssignment.valid_to > now)
    base = db.query(*cols).outerjoin(models.ATAssignment, on_condition)
    if cliente:
        base = base.filter(models.Customer.name.ilike(f"%{cliente}%"))
    if at:
        base = base.filter(models.ATAssignment.technical_advisor.ilike(f"%{at}%"))
    if estandar is not None:
        base = base.filter(models.ATAssignment.standard_visits == estandar)
    if premium is not None:
        base = base.filter(models.ATAssignment.premium_visits == premium)
    if status:
        base = base.filter(models.ATAssignment.status == status)
    return base


@router.get("/control-at/exportar-excel")
async def exportar_control_at_excel(
    cliente: str = Query("", alias="cliente"),
    at: str = Query("", alias="at"),
    estandar: int = Query(None, alias="estandar"),
    premium: int = Query(None, alias="premium"),
    status: str = Query("", alias="status"),
    db: Session = Depends(get_db),
):
    """Exporta el control de asignaciones AT a Excel, con los filtros aplicados."""
    from services.excel import hoja_excel, nombre_con_fecha

    filas_crudas = (
        _control_at_query(db, cliente=cliente, at=at, estandar=estandar,
                          premium=premium, status=status, vigentes=True)
        .order_by(models.Customer.name)
        .all()
    )

    # Se conserva la version mas reciente por cliente, igual que el listado.
    vistos = {}
    for r in filas_crudas:
        previo = vistos.get(r.name)
        if previo is None or (r.assignment_id and (previo.assignment_id is None
                                                   or r.assignment_id > previo.assignment_id)):
            vistos[r.name] = r

    filas = []
    for r in vistos.values():
        std = r.standard_visits or 0
        prem = r.premium_visits or 0
        filas.append([
            r.name, r.plant, r.technical_advisor, std, prem, std + prem,
            r.status,
            r.valid_from.strftime("%d/%m/%Y") if r.valid_from else "",
            r.valid_to.strftime("%d/%m/%Y") if r.valid_to else "Vigente",
        ])

    return hoja_excel(
        "Control AT",
        ["Cliente", "Planta", "Asistente técnico", "Visitas estándar",
         "Visitas premium", "Total asignadas", "Estado", "Vigente desde",
         "Vigente hasta"],
        filas,
        nombre_con_fecha("control-at"),
    )


@router.get("/control-at", response_class=HTMLResponse)
async def control_at_lista(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    cliente: str = Query("", alias="cliente"),
    at: str = Query("", alias="at"),
    estandar: int = Query(None, alias="estandar"),
    premium: int = Query(None, alias="premium"),
    status: str = Query("", alias="status"),
    db: Session = Depends(get_db),
):

    build_base_query = lambda vigentes=True: _control_at_query(
        db, cliente=cliente, at=at, estandar=estandar, premium=premium,
        status=status, vigentes=vigentes)

    base_q = build_base_query(vigentes=True)
    total = base_q.count()
    page, per_page, offset = pg.paginate(page, per_page)
    raw_rows = base_q.order_by(models.Customer.name).offset(offset).limit(per_page).all()

    # deduplicate: keep latest version per customer (highest id)
    seen = {}
    for r in raw_rows:
        prev = seen.get(r.name)
        if prev is None or (r.assignment_id and (prev.assignment_id is None or r.assignment_id > prev.assignment_id)):
            seen[r.name] = r
    rows = list(seen.values())

    use_all_versions = bool(at)
    kpi_q = build_base_query(vigentes=not use_all_versions)
    all_rows = kpi_q.order_by(models.Customer.name).all()
    unique_assignments = {}
    for r in all_rows:
        if r.assignment_id and r.assignment_id not in unique_assignments:
            unique_assignments[r.assignment_id] = r
    unique_rows = list(unique_assignments.values())
    total_std = sum((r.standard_visits or 0) for r in unique_rows)
    total_prem = sum((r.premium_visits or 0) for r in unique_rows)
    total_vis_sum = total_std + total_prem
    total_clientes = len(unique_rows)
    fuera_cronograma = sum(1 for r in unique_rows if r.status == "Fuera de Cronograma")
    names_with_at = [r.name for r in unique_rows if r.name]
    if names_with_at:
        filtered_customer_ids = [
            cid for (cid,) in db.query(models.Customer.id)
            .filter(models.Customer.name.in_(names_with_at))
            .all()
        ]
    else:
        filtered_customer_ids = []

    visit_count_query = db.query(
        models.TechnicalVisit2.form_data["cliente_id"].as_string(),
        func.count(models.TechnicalVisit2.id),
    )
    if filtered_customer_ids:
        str_ids = [str(x) for x in filtered_customer_ids]
        visit_count_query = visit_count_query.filter(
            models.TechnicalVisit2.form_data["cliente_id"].as_string().in_(str_ids)
        )
    visit_count_rows = visit_count_query.group_by(
        models.TechnicalVisit2.form_data["cliente_id"].as_string()
    ).all()
    visit_counts = {int(cid): cnt for cid, cnt in visit_count_rows if cid}
    realizadas_sum = sum(visit_counts.values())
    pendientes_sum = total_vis_sum - realizadas_sum
    avance_pct = round((realizadas_sum / total_vis_sum * 100) if total_vis_sum > 0 else 0)

    at_list = (
        db.query(models.ATAssignment.technical_advisor)
        .filter(or_(models.ATAssignment.valid_to.is_(None), models.ATAssignment.valid_to > datetime.datetime.utcnow()))
        .distinct()
        .order_by(models.ATAssignment.technical_advisor)
        .all()
    )
    at_list = [a[0] for a in at_list if a[0]]

    total_pages = ceil(total / per_page) if total > 0 else 1

    return templates.TemplateResponse(request, 'control_at.html', {
            "request": request,
            "rows": rows,
            "visit_counts": visit_counts,
            "at_list": at_list,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "filters": {
                "cliente": cliente,
                "at": at,
                "estandar": estandar,
                "premium": premium,
                "status": status,
            },
            "kpi": {
                "total_clientes": total_clientes,
                "total_std": total_std,
                "total_prem": total_prem,
                "total_vis_sum": total_vis_sum,
                "realizadas_sum": realizadas_sum,
                "pendientes_sum": pendientes_sum,
                "fuera_cronograma": fuera_cronograma,
                "avance_pct": avance_pct,
            },
            "advisors": kpi_service.get_advisor_names(db),
            "customer_names": [c.name for c in db.query(models.Customer).order_by(models.Customer.name).all()],
            "active_page": "control_at",
        })
