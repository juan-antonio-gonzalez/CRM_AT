from sqlalchemy.orm import Session
import models
from enums import TrackingStatus
import datetime


def list_trackings(db: Session):
    return db.query(models.ActionPlanTracking).filter(
        models.ActionPlanTracking.is_active == True
    ).order_by(models.ActionPlanTracking.created_at.desc()).all()


def get_tracking_stats(trackings: list):
    total = len(trackings)
    pendientes = sum(1 for t in trackings if t.status.lower() in ("pendiente", "pending"))
    en_curso = sum(1 for t in trackings if t.status.lower() in ("en curso", "en_curso", "in_progress", "progress", "en proceso"))
    finalizadas = sum(1 for t in trackings if t.status.lower() in ("finalizado", "finalizada", "done", "completed", "completado"))
    return total, finalizadas, pendientes, en_curso


def update_tracking(db: Session, track_id: int, form_data):
    track = db.query(models.ActionPlanTracking).filter(models.ActionPlanTracking.id == track_id).first()
    if track:
        track.task = form_data.get("task", track.task)
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
