from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import models
from database import get_db
from templating import templates

router = APIRouter(tags=["configuracion"])

ENTITY_MODEL_MAP = {
    "advisor": models.TechnicalAdvisor,
    "designer": models.Designer,
    "commercial": models.CommercialAdvisor,
    "sector": models.IndustrialSector,
    "machine-type": models.MachineType,
    "topic": models.VisitTopic,
    "formado": models.FormadoType,
    "cierre-inferior": models.InferiorClosure,
    "client-name": models.ClientName,
    "plant-name": models.PlantName,
    "visit-type": models.VisitType,
    "distributor-plant": models.DistributorPlant,
    "contact-name": models.ContactName,
    "member-sector": models.MemberSector,
    "tema-calidad": models.QualityTopic,
    "calidad-at": models.QualityAT,
}


def _get_model(entity_type: str):
    return ENTITY_MODEL_MAP.get(entity_type)


@router.get("/configuracion", response_class=HTMLResponse)
async def view_config(request: Request, db: Session = Depends(get_db)):
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    designers = db.query(models.Designer).order_by(models.Designer.name).all()
    commercials = db.query(models.CommercialAdvisor).order_by(models.CommercialAdvisor.name).all()
    sectors = db.query(models.IndustrialSector).order_by(models.IndustrialSector.name).all()
    machine_types = db.query(models.MachineType).order_by(models.MachineType.name).all()
    formado_types = db.query(models.FormadoType).order_by(models.FormadoType.name).all()
    inferior_closure_types = db.query(models.InferiorClosure).order_by(models.InferiorClosure.name).all()
    client_names = db.query(models.ClientName).order_by(models.ClientName.name).all()
    plant_names = db.query(models.PlantName).order_by(models.PlantName.name).all()
    visit_types = db.query(models.VisitType).order_by(models.VisitType.name).all()
    distributor_plants = db.query(models.DistributorPlant).order_by(models.DistributorPlant.name).all()
    quality_topics = db.query(models.QualityTopic).order_by(models.QualityTopic.name).all()
    quality_at_topics = db.query(models.QualityAT).order_by(models.QualityAT.name).all()
    member_sectors = db.query(models.MemberSector).order_by(models.MemberSector.name).all()
    contact_name_items = db.query(models.ContactName).order_by(models.ContactName.name).all()
    return templates.TemplateResponse(request, 'configuracion.html', {
        "request": request,
        "advisors": advisors,
        "designers": designers,
        "commercials": commercials,
        "sectors": sectors,
        "machine_types": machine_types,
        "formado_types": formado_types,
        "inferior_closure_types": inferior_closure_types,
        "client_names": client_names,
        "plant_names": plant_names,
        "visit_types": visit_types,
        "distributor_plants": distributor_plants,
        "quality_topics": quality_topics,
        "quality_at_topics": quality_at_topics,
        "member_sectors": member_sectors,
        "contact_names_list": contact_name_items,
        "active_page": "configuracion"
    })


@router.get("/configuracion/list/{entity_type}")
async def list_config_items(entity_type: str, db: Session = Depends(get_db)):
    model = _get_model(entity_type)
    if not model:
        return JSONResponse({"items": []})
    items = db.query(model).order_by(model.name).all()
    return JSONResponse({"items": [{"id": i.id, "name": i.name, "is_active": getattr(i, 'is_active', True)} for i in items]})


@router.post("/configuracion/add/{entity_type}")
async def add_config_item(entity_type: str, name: str = Form(...), request: Request = None, db: Session = Depends(get_db)):
    model = _get_model(entity_type)
    if model:
        db.add(model(name=name.strip().upper()))
    db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"status": "success", "name": name})
    return RedirectResponse(url="/configuracion", status_code=303)


@router.post("/configuracion/delete/{entity_type}/{item_id}")
async def delete_config_item(entity_type: str, item_id: int, request: Request, db: Session = Depends(get_db)):
    model = _get_model(entity_type)
    if model:
        item = db.query(model).filter(model.id == item_id).first()
        if item:
            from services import soft_delete as sd
            user = getattr(request.state, 'user', None)
            uid = int(user["sub"]) if user else None
            sd.soft_deactivate(db, model, item_id, "Eliminado desde configuración", uid)
    return RedirectResponse(url="/configuracion", status_code=303)


@router.post("/configuracion/edit/{entity_type}/{item_id}")
async def edit_config_item(entity_type: str, item_id: int, name: str = Form(...), db: Session = Depends(get_db)):
    model = _get_model(entity_type)
    if model:
        item = db.query(model).filter(model.id == item_id).first()
        if item:
            item.name = name.strip().upper()
            db.commit()
    return RedirectResponse(url="/configuracion", status_code=303)
