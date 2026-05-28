from sqlalchemy.orm import Session
from fastapi import HTTPException
from starlette.datastructures import UploadFile
from typing import List, Optional
import models
from enums import VisitStatus, TrackingStatus
import datetime
import json
import os
import uuid
from PIL import Image, ImageOps
from io import BytesIO

UPLOAD_VISITAS_DIR = "static/uploads/visitas"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_DIMENSION = 8000
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def process_visit_photos(files: List[UploadFile]) -> list:
    saved_paths = []
    for f in files:
        if not hasattr(f, "filename") or not f.filename:
            continue

        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            continue

        try:
            content = await f.read()
        except Exception:
            continue

        if not content or len(content) > MAX_FILE_SIZE:
            continue

        if len(content) < 64:
            continue

        try:
            img = Image.open(BytesIO(content))
            img.verify()
            img = Image.open(BytesIO(content))

            if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
                continue

            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img = ImageOps.fit(img, (1024, 768), Image.Resampling.LANCZOS)

            filename = f"{uuid.uuid4().hex}.jpg"
            filepath = os.path.join(UPLOAD_VISITAS_DIR, filename)
            os.makedirs(UPLOAD_VISITAS_DIR, exist_ok=True)
            img.save(filepath, "JPEG", quality=85)
            saved_paths.append(f"visitas/{filename}")
        except Exception:
            pass
    return saved_paths


def sync_action_plan(db: Session, visit: models.TechnicalVisit):
    if not visit.action_plan:
        return
    try:
        plan_items = visit.action_plan
        if isinstance(plan_items, str):
            plan_items = json.loads(plan_items)

        existing_tracks = db.query(models.ActionPlanTracking).filter(
            models.ActionPlanTracking.source_visit_id == visit.id
        ).all()
        existing_map = {t.task.strip().lower(): t for t in existing_tracks if t.task}

        status_map = {
            "pending": TrackingStatus.PENDIENTE.value,
            "pendiente": TrackingStatus.PENDIENTE.value,
            "in_progress": TrackingStatus.EN_CURSO.value,
            "in progress": TrackingStatus.EN_CURSO.value,
            "progress": TrackingStatus.EN_CURSO.value,
            "en proceso": TrackingStatus.EN_CURSO.value,
            "done": TrackingStatus.FINALIZADO.value,
            "completed": TrackingStatus.FINALIZADO.value,
            "completado": TrackingStatus.FINALIZADO.value,
            "finalizado": TrackingStatus.FINALIZADO.value,
            "cancelado": TrackingStatus.CANCELADO.value,
            "canceled": TrackingStatus.CANCELADO.value,
        }

        for item in plan_items:
            task_desc = str(item.get("task", "")).strip()
            if not task_desc:
                continue
            task_key = task_desc.lower()
            raw_status = item.get("status", TrackingStatus.PENDIENTE.value)
            norm_status = status_map.get(raw_status, raw_status)
            if task_key in existing_map:
                track = existing_map[task_key]
                track.responsible = item.get("responsible", track.responsible)
                track.due_date = item.get("due_date", track.due_date)
                track.status = norm_status
            else:
                customer_name = visit.customer.name if visit.customer else visit.customer_name_backup
                if not customer_name and visit.customer_id:
                    cust = db.query(models.Customer).filter(models.Customer.id == visit.customer_id).first()
                    customer_name = cust.name if cust else "Desconocido"
                new_track = models.ActionPlanTracking(
                    customer_name=customer_name or "Desconocido",
                    plant=visit.plant,
                    visit_date=visit.date,
                    task=task_desc,
                    responsible=item.get("responsible", ""),
                    due_date=item.get("due_date", ""),
                    status=norm_status,
                    source_visit_id=visit.id
                )
                db.add(new_track)
        db.commit()
    except Exception:
        pass


def create_visit_from_form(db: Session, form_data, customer_name: str, plant_name: str):
    customer = db.query(models.Customer).filter(
        models.Customer.name == customer_name,
        models.Customer.plant == plant_name
    ).first()
    if not customer:
        customer = db.query(models.Customer).filter(models.Customer.name == customer_name).first()
        if not customer:
            return None

    customer_id = customer.id

    action_plan_json = form_data.get("action_plan_json", "[]")
    try:
        action_plan = json.loads(action_plan_json)
    except json.JSONDecodeError:
        action_plan = []

    date_str = form_data.get("date")
    visit_date = datetime.datetime.now(datetime.UTC)
    if date_str:
        try:
            visit_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass

    status = VisitStatus.FINALIZADA.value if form_data.get("save_status") == "final" else VisitStatus.PROGRAMADA.value
    selected_topics = form_data.getlist("topics")

    new_visit = models.TechnicalVisit(
        customer_id=customer_id,
        plant=form_data.get("plant_assigned", ""),
        date=visit_date,
        participants=form_data.get("participants", ""),
        visit_type=form_data.get("visit_type", "Mantenimiento"),
        objective=form_data.get("objective", ""),
        follow_up_previous=form_data.get("follow_up_json", ""),
        findings_quality=form_data.get("findings_quality_json", ""),
        findings_support=form_data.get("findings_support_json", ""),
        conclusions=form_data.get("conclusions", ""),
        detailed_development=form_data.get("detailed_development", ""),
        action_plan=action_plan,
        status=status,
        evidence_photos=[],
        topics=selected_topics,
        technical_advisor=form_data.get("technical_advisor", ""),
        distributor_plant=form_data.get("distributor_plant", "")
    )

    db.add(new_visit)
    db.commit()
    db.refresh(new_visit)
    sync_action_plan(db, new_visit)
    return new_visit


def update_visit_from_form(db: Session, visit_id: int, form_data):
    visit = db.query(models.TechnicalVisit).filter(models.TechnicalVisit.id == visit_id).first()
    if not visit:
        return None

    customer_name = form_data.get("customer_id")
    plant_name = form_data.get("plant")
    customer = db.query(models.Customer).filter(
        models.Customer.name == customer_name,
        models.Customer.plant == plant_name
    ).first()
    if not customer:
        customer = db.query(models.Customer).filter(models.Customer.name == customer_name).first()
        if not customer:
            return None

    action_plan = form_data.get("action_plan_json", "[]")
    status = form_data.get("save_status", "borrador")
    final_status = VisitStatus.PROGRAMADA.value if status == "borrador" else VisitStatus.FINALIZADA.value

    if final_status == VisitStatus.FINALIZADA.value:
        try:
            plan_items = json.loads(action_plan)
            all_done = all(item.get("status") == "done" for item in plan_items)
            if not all_done and len(plan_items) > 0:
                final_status = VisitStatus.PROGRAMADA.value
        except:
            pass

    visit.customer_id = customer.id
    visit.plant = form_data.get("plant", "")
    visit_date_str = form_data.get("date")
    if visit_date_str:
        try:
            visit.date = datetime.datetime.strptime(visit_date_str, "%Y-%m-%d")
        except:
            pass

    visit.participants = form_data.get("participants", "")
    visit.visit_type = form_data.get("visit_type", "")
    visit.objective = form_data.get("objective", "")
    visit.follow_up_previous = form_data.get("follow_up_json", "")
    visit.findings_quality = form_data.get("findings_quality_json", "")
    visit.findings_support = form_data.get("findings_support_json", "")
    visit.conclusions = form_data.get("conclusions", "")
    visit.detailed_development = form_data.get("detailed_development", "")
    visit.topics = form_data.getlist("topics")
    visit.action_plan = action_plan
    visit.status = final_status
    visit.technical_advisor = form_data.get("technical_advisor", "")
    visit.distributor_plant = form_data.get("distributor_plant", "")

    db.commit()
    db.refresh(visit)
    sync_action_plan(db, visit)
    return visit


def delete_visit(db: Session, visit_id: int, user_id: int = None, username: str = None):
    visit = db.query(models.TechnicalVisit).filter(models.TechnicalVisit.id == visit_id).first()
    if visit:
        from services.trash_service import move_to_trash
        move_to_trash(db, "visit", visit_id, {
            "customer_id": visit.customer_id, "plant": visit.plant,
            "date": str(visit.date) if visit.date else None,
            "participants": visit.participants,
            "visit_type": visit.visit_type, "objective": visit.objective,
            "follow_up_previous": visit.follow_up_previous,
            "findings_quality": visit.findings_quality,
            "findings_support": visit.findings_support,
            "conclusions": visit.conclusions,
            "action_plan": visit.action_plan,
            "detailed_development": visit.detailed_development,
            "status": visit.status,
            "customer_name_backup": visit.customer_name_backup,
            "topics": visit.topics,
            "technical_advisor": visit.technical_advisor,
            "distributor_plant": visit.distributor_plant,
        }, user_id, username, f"Visita #{visit.id}")
        if visit.evidence_photos:
            photos = visit.evidence_photos
            if isinstance(photos, str):
                try:
                    photos = json.loads(photos)
                except:
                    photos = []
            for photo_path in photos:
                try:
                    filename = photo_path.split("/")[-1]
                    full_path = os.path.join(UPLOAD_VISITAS_DIR, filename)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                except:
                    pass
        db.delete(visit)
        db.commit()
    return visit


def get_visit(db: Session, visit_id: int):
    visit = db.query(models.TechnicalVisit).filter(models.TechnicalVisit.id == visit_id).first()
    if not visit:
        return None
    return visit


def list_visits(db: Session):
    return db.query(models.TechnicalVisit).order_by(models.TechnicalVisit.date.desc()).all()


def get_agenda_events(db: Session):
    visitas = db.query(models.TechnicalVisit).all()
    events = []
    for v in visitas:
        color = "#1a57db"
        if v.status == VisitStatus.FINALIZADA.value:
            color = "#10b981"
        elif v.status == VisitStatus.CANCELADA.value:
            color = "#ef4444"
        elif v.status == VisitStatus.PROGRAMADA.value:
            color = "#f59e0b"
        events.append({
            "id": v.id,
            "title": f"{v.customer.name if v.customer else v.customer_name_backup} - {v.visit_type}",
            "start": v.date.isoformat(),
            "status": v.status,
            "color": color,
            "description": v.objective
        })
    return events


def update_visit_status(db: Session, visit_id: int, new_status: str, reason: str = None):
    visit = get_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    visit.status = new_status
    if new_status == VisitStatus.CANCELADA.value:
        visit.cancellation_reason = reason
    db.commit()
    return {"message": "Estado actualizado correctamente"}
