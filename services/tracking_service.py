from sqlalchemy.orm import Session
from sqlalchemy import func
import models
import datetime
from services import pagination as pg


def list_trackings(db: Session):
    return db.query(models.ActionPlanTracking).filter(
        models.ActionPlanTracking.is_active == True
    ).order_by(models.ActionPlanTracking.created_at.desc()).all()


def paginate_trackings(db: Session, page: int = 1, per_page: int = 10):
    base = db.query(models.ActionPlanTracking).filter(
        models.ActionPlanTracking.is_active == True
    )
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


def update_tracking(db: Session, track_id: int, form_data):
    track = db.query(models.ActionPlanTracking).filter(models.ActionPlanTracking.id == track_id).first()
    if track:
        track.task = form_data.get("task", track.task)
        track.et_number = form_data.get("et_number", track.et_number)
        track.responsible = form_data.get("responsible", track.responsible)
        track.due_date = form_data.get("due_date", track.due_date)
        track.status = form_data.get("status", track.status)
        track.observations = form_data.get("observations", track.observations)
        track.updated_at = datetime.datetime.now(datetime.UTC)
        db.commit()


def delete_tracking(db: Session, track_id: int):
    track = db.query(models.ActionPlanTracking).filter(models.ActionPlanTracking.id == track_id).first()
    if track:
        track.is_active = False
        db.commit()
