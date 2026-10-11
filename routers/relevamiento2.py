from fastapi import APIRouter, Request, Depends, Query, UploadFile, File
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import models
from database import get_db
from services import pagination as pg
from services.utils import safe_json_loads
from services.customer_service import list_customers
import datetime
import os
import uuid
from PIL import Image, UnidentifiedImageError
import io
from templating import templates

router = APIRouter(tags=["relevamiento2"])

def _relevamiento2_query(db, cliente="", asistente=""):
    """Consulta de relevamientos con los filtros del listado."""
    q = db.query(models.TechnicalSurveyV2).options(
        joinedload(models.TechnicalSurveyV2.machine),
        joinedload(models.TechnicalSurveyV2.customer),
    )
    if cliente:
        q = q.filter(models.TechnicalSurveyV2.customer_id == int(cliente))
    if asistente:
        q = q.filter(
            models.TechnicalSurveyV2.form_data["technical_advisor"].as_string() == asistente)
    return q




@router.get("/relevamiento2/exportar-excel")
async def exportar_relevamiento2_excel(
    cliente: str = Query("", alias="cliente"),
    asistente: str = Query("", alias="asistente"),
    db: Session = Depends(get_db),
):
    """Exporta el listado filtrado de relevamientos a Excel."""
    from services.excel import hoja_excel, nombre_con_fecha

    relevamientos = (
        _relevamiento2_query(db, cliente=cliente, asistente=asistente)
        .order_by(models.TechnicalSurveyV2.id.desc())
        .all()
    )

    filas = []
    for r in relevamientos:
        fd = r.form_data or {}
        filas.append([
            r.fecha,
            fd.get("cliente_nombre") or (r.customer.name if r.customer else ""),
            r.machine.model if r.machine else "",
            r.machine.serial_number if r.machine else "",
            fd.get("technical_advisor", ""),
            r.status,
        ])

    return hoja_excel(
        "Relevamientos",
        ["Fecha", "Cliente", "Máquina", "Nº de serie", "Asistente técnico", "Estado"],
        filas,
        nombre_con_fecha("relevamientos"),
    )


@router.get("/relevamiento2", response_class=HTMLResponse)
async def relevamiento2_lista(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    cliente: str = Query("", alias="cliente"),
    asistente: str = Query("", alias="asistente"),
    db: Session = Depends(get_db)
):
    page, per_page, offset = pg.paginate(page, per_page)

    # ── Surveys query (for table rows) ──
    # Eager-load the related rows: the listing template reads s.machine and
    # s.customer for every row (previously one SELECT per row).
    q = db.query(models.TechnicalSurveyV2).options(
        joinedload(models.TechnicalSurveyV2.machine),
        joinedload(models.TechnicalSurveyV2.customer),
    )
    if cliente:
        q = q.filter(models.TechnicalSurveyV2.customer_id == int(cliente))
    if asistente:
        q = q.filter(models.TechnicalSurveyV2.form_data["technical_advisor"].as_string() == asistente)
    total = q.count()
    surveys = q.order_by(
        models.TechnicalSurveyV2.id.desc()
    ).offset(offset).limit(per_page).all()

    # ── Machine-based KPIs (all respond to filters) ──
    # pendientes = machines with NO survey
    # total_relevados = machines with ≥1 survey
    # completados = machines whose latest survey is Finalizado
    # en_proceso  = machines whose latest survey is En proceso

    # Build filtered machine set
    machine_q = db.query(models.Machine).outerjoin(
        models.Customer, models.Machine.customer_id == models.Customer.id
    )
    if cliente:
        machine_q = machine_q.filter(models.Machine.customer_id == int(cliente))
    if asistente:
        machine_q = machine_q.filter(models.Customer.technical_advisor == asistente)
    all_machine_ids = set(r[0] for r in machine_q.with_entities(models.Machine.id).all())

    # Build filtered surveys (same filters) to determine latest status per machine
    surv_q = db.query(models.TechnicalSurveyV2).options(
        joinedload(models.TechnicalSurveyV2.machine),
        joinedload(models.TechnicalSurveyV2.customer),
    )
    if cliente:
        surv_q = surv_q.filter(models.TechnicalSurveyV2.customer_id == int(cliente))
    if asistente:
        surv_q = surv_q.filter(models.TechnicalSurveyV2.machine_id.in_(all_machine_ids))
    all_surveys = surv_q.all()

    # Latest survey per machine (by id)
    latest_survey = {}
    for s in all_surveys:
        if s.machine_id not in latest_survey or s.id > latest_survey[s.machine_id].id:
            latest_survey[s.machine_id] = s

    surveyed_machine_ids = set(latest_survey.keys())
    total_relevados = len(surveyed_machine_ids & all_machine_ids)
    completados = sum(1 for m_id in surveyed_machine_ids if latest_survey[m_id].status == "Finalizado")
    en_proceso = sum(1 for m_id in surveyed_machine_ids if latest_survey[m_id].status == "En proceso")
    pendientes = len(all_machine_ids) - total_relevados

    # ── Shared data ──
    customers = list_customers(db)
    advisors = [a.name for a in db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()]
    plantas = sorted(set(c.plant for c in db.query(models.Customer).all() if c.plant))
    lineas = sorted(set(m.line for m in db.query(models.Machine).all() if m.line))

    return templates.TemplateResponse(request, 'relevamiento2_lista.html', {
        "request": request,
        "surveys": surveys,
        "pagination": pg.build_pagination(page, per_page, total),
        "stats": {
            "pendientes": pendientes,
            "total": total_relevados,
            "completados": completados,
            "en_proceso": en_proceso,
        },
        "customers": customers,
        "advisors": advisors,
        "plantas": plantas,
        "lineas": lineas,
        "selected_customer_id": cliente,
        "selected_asistente": asistente,
        "active_page": "relevamiento2",
    })


@router.get("/relevamiento2/nuevo", response_class=HTMLResponse)
async def nuevo_relevamiento2(
    request: Request,
    machine_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    clientes = list_customers(db)
    maquinas = db.query(models.Machine).all()
    tecnicos = db.query(models.TechnicalAdvisor).all()
    formado_types = db.query(models.FormadoType).order_by(models.FormadoType.name).all()
    closure_types = db.query(models.InferiorClosure).order_by(models.InferiorClosure.name).all()
    preselected_machine = None
    preselected_customer = None
    if machine_id:
        preselected_machine = db.query(models.Machine).filter(models.Machine.id == machine_id).first()
        if preselected_machine and preselected_machine.customer_id:
            preselected_customer = preselected_machine.customer_id
    return templates.TemplateResponse(request, 'nuevo_relevamiento2.html', {
        "request": request,
        "survey": None,
        "form_data": None,
        "title": "Nuevo Relevamiento Técnico",
        "action_url": "/relevamiento2/nuevo",
        "active_page": "relevamiento2",
        "clientes": clientes,
        "maquinas": maquinas,
        "tecnicos": tecnicos,
        "formado_types": formado_types,
        "closure_types": closure_types,
        "preselected_machine": preselected_machine.id if preselected_machine else None,
        "preselected_customer": preselected_customer,
    })


@router.post("/relevamiento2/nuevo")
async def create_relevamiento2(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    data = safe_json_loads(form.get("form_data"))

    fecha = data.get("fecha", "") or ""
    estado = data.get("status", "En proceso")
    customer_id = data.get("customer_id") or None
    machine_id = data.get("machine_id") or None

    new_survey = models.TechnicalSurveyV2(
        customer_id=customer_id,
        machine_id=machine_id,
        fecha=fecha,
        status=estado,
        form_data=data,
    )
    db.add(new_survey)
    db.commit()
    db.refresh(new_survey)

    return RedirectResponse(url="/relevamiento2", status_code=303)


@router.get("/relevamiento2/{survey_id}/editar", response_class=HTMLResponse)
async def editar_relevamiento2(request: Request, survey_id: int, db: Session = Depends(get_db)):
    survey = db.query(models.TechnicalSurveyV2).filter(models.TechnicalSurveyV2.id == survey_id).first()
    if not survey:
        return RedirectResponse(url="/relevamiento2", status_code=303)

    clientes = list_customers(db)
    maquinas = db.query(models.Machine).all()
    tecnicos = db.query(models.TechnicalAdvisor).all()
    formado_types = db.query(models.FormadoType).order_by(models.FormadoType.name).all()
    closure_types = db.query(models.InferiorClosure).order_by(models.InferiorClosure.name).all()
    return templates.TemplateResponse(request, 'nuevo_relevamiento2.html', {
        "request": request,
        "survey": survey,
        "form_data": survey.form_data or {},
        "title": f"Editar Relevamiento #{survey.id}",
        "action_url": f"/relevamiento2/{survey_id}/editar",
        "active_page": "relevamiento2",
        "clientes": clientes,
        "maquinas": maquinas,
        "tecnicos": tecnicos,
        "formado_types": formado_types,
        "closure_types": closure_types,
    })


@router.post("/relevamiento2/{survey_id}/editar")
async def save_editar_relevamiento2(survey_id: int, request: Request, db: Session = Depends(get_db)):
    survey = db.query(models.TechnicalSurveyV2).filter(models.TechnicalSurveyV2.id == survey_id).first()
    if not survey:
        return RedirectResponse(url="/relevamiento2", status_code=303)

    form = await request.form()
    data = safe_json_loads(form.get("form_data"))

    survey.customer_id = data.get("customer_id") or None
    survey.machine_id = data.get("machine_id") or None
    survey.fecha = data.get("fecha", "") or ""
    survey.status = data.get("status", "En proceso")
    survey.form_data = data
    survey.updated_at = datetime.datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/relevamiento2", status_code=303)


@router.post("/upload-foto")
async def upload_foto(request: Request, file: UploadFile = File(...)):
    if not file.filename:
        return JSONResponse({"error": "No file"}, status_code=400)
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    upload_dir = "static/uploads/relevamiento2"
    os.makedirs(upload_dir, exist_ok=True)
    content = await file.read()
    try:
        img = Image.open(io.BytesIO(content))
        if img.width > 1200:
            ratio = 1200 / img.width
            new_h = int(img.height * ratio)
            img = img.resize((1200, new_h), Image.LANCZOS)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80, optimize=True)
        filename = f"{uuid.uuid4().hex}.jpg"
        path = os.path.join(upload_dir, filename)
        with open(path, "wb") as f:
            f.write(buf.getvalue())
    except UnidentifiedImageError:
        filename = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(upload_dir, filename)
        with open(path, "wb") as f:
            f.write(content)
    return JSONResponse({"path": f"/{upload_dir}/{filename}"})


@router.post("/eliminar-foto")
async def eliminar_foto(request: Request):
    data = await request.json()
    path = data.get("path", "")
    if path.startswith("/static/upload"):
        full = path.lstrip("/")
        if os.path.exists(full):
            os.remove(full)
    return JSONResponse({"ok": True})


@router.post("/eliminar-relevamiento2/{survey_id}")
async def delete_relevamiento2(survey_id: int, request: Request, db: Session = Depends(get_db)):
    survey = db.query(models.TechnicalSurveyV2).filter(models.TechnicalSurveyV2.id == survey_id).first()
    if survey:
        from services.trash_service import move_to_trash
        user = getattr(request.state, 'user', None)
        uid = int(user["sub"]) if user else None
        uname = user.get("username") if user else None
        fd = survey.form_data or {}
        mach = survey.machine
        cust = survey.customer
        move_to_trash(db, "survey2", survey.id, {
            "id": survey.id,
            "customer_id": survey.customer_id,
            "machine_id": survey.machine_id,
            "fecha": survey.fecha,
            "status": survey.status,
            "form_data": fd,
            "cliente_nombre": fd.get("cliente_nombre", cust.name if cust else ""),
            "cliente_planta": fd.get("cliente_planta", cust.plant if cust else ""),
            "maquina_nombre": fd.get("maquina_nombre", f"{mach.brand} {mach.model} ({mach.serial_number})" if mach else ""),
        }, uid, uname, f"Relevamiento #{survey.id}")
        # Clean up foto files
        for key in ['fotos_e1', 'fotos_e2', 'fotos_e3']:
            for p in (fd.get(key) or []):
                if isinstance(p, str) and p.startswith("/static/uploads/"):
                    full = p.lstrip("/")
                    if os.path.exists(full):
                        os.remove(full)
        db.delete(survey)
        db.commit()
    return RedirectResponse(url="/relevamiento2", status_code=303)
