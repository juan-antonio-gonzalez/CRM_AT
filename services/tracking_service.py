from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import models
import datetime
from services import pagination as pg
from enums import normalize_tracking_status


def list_trackings(db: Session):
    return db.query(models.ActionPlanTracking).filter(
        models.ActionPlanTracking.is_active == True
    ).order_by(models.ActionPlanTracking.created_at.desc()).all()


def query_trackings(db: Session, q=None, estado=None):
    """Consulta de tareas de seguimiento con los filtros del listado.

    La comparten el listado y la exportación.
    """
    base = db.query(models.ActionPlanTracking).filter(
        models.ActionPlanTracking.is_active == True
    )

    if q and q.strip():
        patron = f"%{q.strip()}%"
        base = base.filter(or_(
            models.ActionPlanTracking.task.ilike(patron),
            models.ActionPlanTracking.customer_name.ilike(patron),
            models.ActionPlanTracking.plant.ilike(patron),
            models.ActionPlanTracking.et_number.ilike(patron),
            models.ActionPlanTracking.responsible.ilike(patron),
            models.ActionPlanTracking.observations.ilike(patron),
        ))

    if estado and estado.strip():
        base = base.filter(
            func.lower(models.ActionPlanTracking.status) == normalize_tracking_status(estado).lower()
        )

    return base


def paginate_trackings(db: Session, page: int = 1, per_page: int = 10,
                       q: str = None, estado: str = None):
    """Lista paginada de tareas, con búsqueda y filtro por estado.

    Antes no aceptaba filtros: con muchas tareas no había forma de encontrar una
    acción concreta ni de ver sólo las pendientes.
    """

    base = query_trackings(db, q=q, estado=estado)

    total = base.count()
    page, per_page, offset = pg.paginate(page, per_page)
    items = base.order_by(
        models.ActionPlanTracking.created_at.desc()
    ).offset(offset).limit(per_page).all()
    return items, pg.build_pagination(page, per_page, total)


def get_tracking_stats(db: Session):
    total = db.query(func.count(models.ActionPlanTracking.id)).filter(
        models.ActionPlanTracking.is_active == True
    ).scalar() or 0
    pendientes = db.query(func.count(models.ActionPlanTracking.id)).filter(
        models.ActionPlanTracking.is_active == True,
        func.lower(models.ActionPlanTracking.status).in_(["pendiente", "pending"])
    ).scalar() or 0
    en_curso = db.query(func.count(models.ActionPlanTracking.id)).filter(
        models.ActionPlanTracking.is_active == True,
        func.lower(models.ActionPlanTracking.status).in_(
            ["en curso", "en_curso", "in_progress", "progress", "en proceso"]
        )
    ).scalar() or 0
    finalizadas = db.query(func.count(models.ActionPlanTracking.id)).filter(
        models.ActionPlanTracking.is_active == True,
        func.lower(models.ActionPlanTracking.status).in_(
            ["finalizado", "finalizada", "done", "completed", "completado"]
        )
    ).scalar() or 0
    return total, finalizadas, pendientes, en_curso


def create_tracking(db: Session, form_data) -> models.ActionPlanTracking:
    """Crea una tarea de plan de acción cargada a mano.

    Hasta ahora las tareas sólo nacían de la tabla 9 de una visita técnica
    (``visits2.sync_action_plan``), así que no había forma de registrar una
    acción que surgiera de una llamada, un correo o una reunión. Faltaba la "C"
    del CRUD en este módulo.
    """

    task = (form_data.get("task") or "").strip()
    if not task:
        raise ValueError("La tarea es obligatoria")

    record = models.ActionPlanTracking(
        customer_name=(form_data.get("customer_name") or "").strip() or None,
        plant=(form_data.get("plant") or "").strip() or None,
        et_number=(form_data.get("et_number") or "").strip() or None,
        task=task,
        responsible=(form_data.get("responsible") or "").strip() or None,
        due_date=(form_data.get("due_date") or "").strip() or None,
        status=normalize_tracking_status(form_data.get("status")),
        observations=(form_data.get("observations") or "").strip() or None,
        visit_date=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        is_active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_tracking(db: Session, track_id: int, form_data):

    track = db.query(models.ActionPlanTracking).filter(models.ActionPlanTracking.id == track_id).first()
    if track:
        track.task = form_data.get("task", track.task)
        track.et_number = form_data.get("et_number", track.et_number)
        track.responsible = form_data.get("responsible", track.responsible)
        track.due_date = form_data.get("due_date", track.due_date)
        if form_data.get("status"):
            track.status = normalize_tracking_status(form_data.get("status"))
        track.observations = form_data.get("observations", track.observations)
        if form_data.get("customer_name") is not None:
            track.customer_name = form_data.get("customer_name")
        track.updated_at = datetime.datetime.now(datetime.UTC)
        db.commit()
    return track


def delete_tracking(db: Session, track_id: int):
    track = db.query(models.ActionPlanTracking).filter(models.ActionPlanTracking.id == track_id).first()
    if track:
        track.is_active = False
        db.commit()
