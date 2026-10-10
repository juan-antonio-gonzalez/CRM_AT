from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import models
from enums import RelevamientoStatus, CustomerStatus
from services.utils import month_buckets
import datetime


def _base_visit_query(db: Session, at: str = "", cliente: str = ""):
    q = db.query(models.TechnicalVisit2)
    if at:
        q = q.filter(models.TechnicalVisit2.form_data["at"].as_string() == at)
    if cliente:
        q = q.filter(
            models.TechnicalVisit2.form_data["cliente_id"].as_string() == str(cliente)
        )
    return q


def _filter_visit_form_data(db: Session, at: str = "", cliente: str = "",
                            fecha_desde: str = "", fecha_hasta: str = ""):
    q = db.query(models.TechnicalVisit2.form_data, models.TechnicalVisit2.fecha)
    if at:
        q = q.filter(models.TechnicalVisit2.form_data["at"].as_string() == at)
    if cliente:
        q = q.filter(
            models.TechnicalVisit2.form_data["cliente_id"].as_string() == str(cliente)
        )
    if fecha_desde:
        q = q.filter(models.TechnicalVisit2.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(models.TechnicalVisit2.fecha <= fecha_hasta)
    return q


def _row_matches(row, tema: str = "", impacto: str = ""):
    if tema:
        row_tema = row[1] if len(row) > 1 else ""
        if tema.lower() not in row_tema.lower():
            return False
    if impacto:
        row_impacto = row[3] if len(row) > 3 else ""
        if row_impacto != impacto:
            return False
    return True


def get_clientes_stats(db: Session, at: str = ""):
    base = db.query(models.Customer)
    if at:
        base = base.filter(models.Customer.technical_advisor == at)

    total = base.count()
    activos = base.filter(
        models.Customer.status == CustomerStatus.CLIENTE.value
    ).count()
    prospectos = base.filter(
        models.Customer.status == CustomerStatus.PROSPECTO.value
    ).count()

    sector_rows = base.with_entities(
        models.Customer.industry_sector, func.count(models.Customer.id)
    ).group_by(models.Customer.industry_sector).order_by(func.count(models.Customer.id).desc()).all()
    por_sector = [{"sector": r[0] or "Sin sector", "cant": r[1]} for r in sector_rows]

    ciudad_rows = base.with_entities(
        models.Customer.city, func.count(models.Customer.id)
    ).group_by(models.Customer.city).order_by(func.count(models.Customer.id).desc()).all()
    por_ciudad = [{"ciudad": r[0] or "Sin ciudad", "cant": r[1]} for r in ciudad_rows]

    at_rows = base.with_entities(
        models.Customer.technical_advisor, func.count(models.Customer.id)
    ).group_by(models.Customer.technical_advisor).order_by(func.count(models.Customer.id).desc()).all()
    por_at = [{"at": r[0] or "Sin asignar", "cant": r[1]} for r in at_rows]

    return {
        "total": total,
        "activos": activos,
        "prospectos": prospectos,
        "por_sector": por_sector,
        "por_ciudad": por_ciudad,
        "por_at": por_at,
    }


def get_visitas_stats(db: Session, today: datetime.datetime,
                      at: str = "", cliente: str = "",
                      fecha_desde: str = "", fecha_hasta: str = "",
                      tema: str = "", impacto: str = "",
                      tipo_producto: str = "", planta: str = ""):
    vq = _base_visit_query(db, at, cliente)
    if fecha_desde:
        vq = vq.filter(models.TechnicalVisit2.fecha >= fecha_desde)
    if fecha_hasta:
        vq = vq.filter(models.TechnicalVisit2.fecha <= fecha_hasta)
    total = vq.count()
    count_borrador = vq.filter(models.TechnicalVisit2.status == "Borrador").count()
    count_finalizado = vq.filter(models.TechnicalVisit2.status == "Finalizado").count()

    at_q = db.query(
        func.coalesce(func.sum(models.ATAssignment.standard_visits), 0) +
        func.coalesce(func.sum(models.ATAssignment.premium_visits), 0)
    ).filter(models.ATAssignment.valid_to.is_(None))
    if at:
        at_q = at_q.filter(models.ATAssignment.technical_advisor == at)
    total_asignadas_at = at_q.scalar() or 0

    # Monthly trend from filtered visits
    recent_visits = vq.with_entities(models.TechnicalVisit2.fecha).filter(
        models.TechnicalVisit2.fecha != ''
    ).all()
    visits_by_month_map = {}
    for (f,) in recent_visits:
        if f:
            try:
                key = f[:7]
                visits_by_month_map[key] = visits_by_month_map.get(key, 0) + 1
            except Exception:
                pass

    chart_months_labels = []
    chart_visits_data = []
    # Real calendar-month buckets. The previous implementation subtracted
    # i * 30 days, which skipped February and duplicated January.
    for month_key, label, _first, _last in month_buckets(today, 6):
        chart_months_labels.append(label)
        chart_visits_data.append(visits_by_month_map.get(month_key, 0))

    # Process form_data with all filters
    all_v2 = _filter_visit_form_data(db, at, cliente, fecha_desde, fecha_hasta).all()
    obj_count = {}
    at_visit_count = {}
    calidad_temas = {}
    asistencia_temas = {}
    total_calidad_rows = 0
    total_asistencia_rows = 0

    impacto_calidad = {"ALTA": 0, "MEDIA": 0, "BAJA": 0}
    impacto_asistencia = {"ALTA": 0, "MEDIA": 0, "BAJA": 0}
    impacto_por_tema_calidad = {}
    impacto_por_tema_asistencia = {}

    # Collect all unique values for filter dropdowns
    all_temas_calidad = set()
    all_temas_asistencia = set()
    all_tipos_producto = set()
    all_plantas = set()

    for (fd, _fecha) in all_v2:
        if not fd or not isinstance(fd, dict):
            continue

        tp = fd.get("tipo_producto", "")
        pl = fd.get("planta", "")
        if tp:
            all_tipos_producto.add(tp)
        if pl:
            all_plantas.add(pl)

        if tipo_producto and tp != tipo_producto:
            continue
        if planta and pl != planta:
            continue
        objs = fd.get("objetivo", [])
        if isinstance(objs, list):
            for o in objs:
                obj_count[o] = obj_count.get(o, 0) + 1
        at_name = fd.get("at") or "Sin asignar"
        at_visit_count[at_name] = at_visit_count.get(at_name, 0) + 1
        tables = fd.get("tables", {})

        # Table 6
        t6 = tables.get("6", [])
        for row in t6:
            if not _row_matches(row, tema, impacto):
                continue
            total_calidad_rows += 1
            _tema = row[1] if len(row) > 1 else "Sin tema"
            all_temas_calidad.add(_tema)
            calidad_temas[_tema] = calidad_temas.get(_tema, 0) + 1
            _impacto = row[3] if len(row) > 3 else ""
            if _impacto in impacto_calidad:
                impacto_calidad[_impacto] += 1
            impacto_por_tema_calidad.setdefault(_tema, {"ALTA": 0, "MEDIA": 0, "BAJA": 0})
            if _impacto in impacto_por_tema_calidad[_tema]:
                impacto_por_tema_calidad[_tema][_impacto] += 1

        # Table 7
        t7 = tables.get("7", [])
        for row in t7:
            if not _row_matches(row, tema, impacto):
                continue
            total_asistencia_rows += 1
            _tema = row[1] if len(row) > 1 else "Sin tema"
            all_temas_asistencia.add(_tema)
            asistencia_temas[_tema] = asistencia_temas.get(_tema, 0) + 1
            _impacto = row[3] if len(row) > 3 else ""
            if _impacto in impacto_asistencia:
                impacto_asistencia[_impacto] += 1
            impacto_por_tema_asistencia.setdefault(_tema, {"ALTA": 0, "MEDIA": 0, "BAJA": 0})
            if _impacto in impacto_por_tema_asistencia[_tema]:
                impacto_por_tema_asistencia[_tema][_impacto] += 1

    sorted_objs = sorted(obj_count.items(), key=lambda x: x[1], reverse=True)[:5]
    calidad_sorted = sorted(calidad_temas.items(), key=lambda x: x[1], reverse=True)[:8]
    asistencia_sorted = sorted(asistencia_temas.items(), key=lambda x: x[1], reverse=True)[:8]

    avance_pct = round((count_finalizado / total_asignadas_at * 100), 1) if total_asignadas_at > 0 else 0

    return {
        "total": total,
        "borrador": count_borrador,
        "finalizado": count_finalizado,
        "total_asignadas_at": total_asignadas_at,
        "avance_pct": avance_pct,
        "objetivos": sorted_objs,
        "objetivos_labels": [o[0] for o in sorted_objs],
        "objetivos_data": [o[1] for o in sorted_objs],
        "tendencia_meses": chart_months_labels,
        "tendencia_datos": chart_visits_data,
        "por_at": sorted(at_visit_count.items(), key=lambda x: x[1], reverse=True),
        "calidad_temas": calidad_sorted,
        "calidad_labels": [t[0] for t in calidad_sorted],
        "calidad_data": [t[1] for t in calidad_sorted],
        "asistencia_temas": asistencia_sorted,
        "asistencia_labels": [t[0] for t in asistencia_sorted],
        "asistencia_data": [t[1] for t in asistencia_sorted],
        "total_calidad": total_calidad_rows,
        "total_asistencia": total_asistencia_rows,
        "impacto_calidad": impacto_calidad,
        "impacto_asistencia": impacto_asistencia,
        "impacto_por_tema_calidad": impacto_por_tema_calidad,
        "impacto_por_tema_asistencia": impacto_por_tema_asistencia,
        "all_temas_calidad": sorted(all_temas_calidad),
        "all_temas_asistencia": sorted(all_temas_asistencia),
        "all_tipos_producto": sorted(all_tipos_producto),
        "all_plantas": sorted(all_plantas),
    }


def get_maquinas_stats(db: Session, at: str = "", cliente: str = ""):
    base = db.query(models.Machine).join(
        models.Customer, models.Machine.customer_id == models.Customer.id,
        isouter=True
    )
    if at:
        base = base.filter(models.Customer.technical_advisor == at)
    if cliente:
        base = base.filter(models.Machine.customer_id == int(cliente))

    total = base.count()
    completed_surveys = base.filter(
        models.Machine.relevamiento_status == RelevamientoStatus.COMPLETADO.value
    ).count()

    tipo_rows = base.with_entities(
        models.Machine.machine_type, func.count(models.Machine.id)
    ).group_by(models.Machine.machine_type).order_by(func.count(models.Machine.id).desc()).all()
    estado_rows = base.with_entities(
        models.Machine.status, func.count(models.Machine.id)
    ).group_by(models.Machine.status).order_by(func.count(models.Machine.id).desc()).all()
    relev_rows = base.with_entities(
        models.Machine.relevamiento_status, func.count(models.Machine.id)
    ).group_by(models.Machine.relevamiento_status).order_by(func.count(models.Machine.id).desc()).all()

    return {
        "total": total,
        "relevamiento_completado": completed_surveys,
        "survey_progress": round((completed_surveys / total * 100), 1) if total > 0 else 0,
        "por_tipo": [{"tipo": r[0] or "Sin tipo", "cant": r[1]} for r in tipo_rows],
        "por_estado": [{"estado": r[0] or "Sin estado", "cant": r[1]} for r in estado_rows],
        "por_relevamiento": [{"estado": r[0] or "Sin estado", "cant": r[1]} for r in relev_rows],
    }


def get_minutas_stats(db: Session, at: str = "", cliente: str = ""):
    base = db.query(models.MeetingMinutes)
    total = base.count()
    min_borrador = base.filter(models.MeetingMinutes.status == "Borrador").count()
    min_finalizado = base.filter(models.MeetingMinutes.status == "Finalizado").count()

    all_min_form = base.with_entities(models.MeetingMinutes.form_data).all()
    min_tipo_rows = {}
    for (mfd,) in all_min_form:
        if mfd and isinstance(mfd, dict):
            tipo = mfd.get("tipoReunion") or "Sin tipo"
            min_tipo_rows[tipo] = min_tipo_rows.get(tipo, 0) + 1

    return {
        "total": total,
        "borrador": min_borrador,
        "finalizado": min_finalizado,
        "por_tipo": sorted(min_tipo_rows.items(), key=lambda x: x[1], reverse=True),
    }
