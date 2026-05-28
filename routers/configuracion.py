from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import models
from database import get_db

router = APIRouter(tags=["configuracion"])
templates = Jinja2Templates(directory="templates")


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
    return templates.TemplateResponse("configuracion.html", {
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
        "active_page": "configuracion"
    })


@router.get("/configuracion/list/{entity_type}")
async def list_config_items(entity_type: str, db: Session = Depends(get_db)):
    model_map = {
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
    }
    model = model_map.get(entity_type)
    if not model:
        return JSONResponse({"items": []})
    items = db.query(model).order_by(model.name).all()
    return JSONResponse({"items": [{"id": i.id, "name": i.name} for i in items]})


@router.post("/configuracion/add/{entity_type}")
async def add_config_item(entity_type: str, name: str = Form(...), request: Request = None, db: Session = Depends(get_db)):
    if entity_type == "advisor":
        db.add(models.TechnicalAdvisor(name=name))
    elif entity_type == "designer":
        db.add(models.Designer(name=name))
    elif entity_type == "commercial":
        db.add(models.CommercialAdvisor(name=name))
    elif entity_type == "sector":
        db.add(models.IndustrialSector(name=name))
    elif entity_type == "machine-type":
        db.add(models.MachineType(name=name))
    elif entity_type == "topic":
        db.add(models.VisitTopic(name=name))
    elif entity_type == "formado":
        db.add(models.FormadoType(name=name))
    elif entity_type == "cierre-inferior":
        db.add(models.InferiorClosure(name=name))
    elif entity_type == "client-name":
        db.add(models.ClientName(name=name))
    elif entity_type == "plant-name":
        db.add(models.PlantName(name=name))
    elif entity_type == "visit-type":
        db.add(models.VisitType(name=name))
    elif entity_type == "distributor-plant":
        db.add(models.DistributorPlant(name=name))
    db.commit()

    # Return JSON for AJAX requests, redirect for normal form posts
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"status": "success", "name": name})
    return RedirectResponse(url="/configuracion", status_code=303)


@router.post("/configuracion/delete/{entity_type}/{item_id}")
async def delete_config_item(entity_type: str, item_id: int, request: Request, db: Session = Depends(get_db)):
    model = None
    type_label = entity_type
    if entity_type == "advisor":
        model = models.TechnicalAdvisor
        type_label = "advisor"
    elif entity_type == "designer":
        model = models.Designer
        type_label = "designer"
    elif entity_type == "commercial":
        model = models.CommercialAdvisor
        type_label = "commercial"
    elif entity_type == "sector":
        model = models.IndustrialSector
        type_label = "sector"
    elif entity_type == "machine-type":
        model = models.MachineType
        type_label = "machine-type"
    elif entity_type == "topic":
        model = models.VisitTopic
        type_label = "topic"
    elif entity_type == "formado":
        model = models.FormadoType
        type_label = "formado"
    elif entity_type == "cierre-inferior":
        model = models.InferiorClosure
        type_label = "cierre-inferior"
    elif entity_type == "client-name":
        model = models.ClientName
        type_label = "client-name"
    elif entity_type == "plant-name":
        model = models.PlantName
        type_label = "plant-name"
    elif entity_type == "visit-type":
        model = models.VisitType
        type_label = "visit-type"
    elif entity_type == "distributor-plant":
        model = models.DistributorPlant
        type_label = "distributor-plant"

    if model:
        item = db.query(model).filter(model.id == item_id).first()
        if item:
            from services.trash_service import move_to_trash
            user = getattr(request.state, 'user', None)
            uid = int(user["sub"]) if user else None
            uname = user.get("username") if user else None
            move_to_trash(db, type_label, item_id, {
                "name": item.name,
            }, uid, uname, item.name)
            db.delete(item)
            db.commit()
    return RedirectResponse(url="/configuracion", status_code=303)


@router.post("/configuracion/edit/{entity_type}/{item_id}")
async def edit_config_item(entity_type: str, item_id: int, name: str = Form(...), db: Session = Depends(get_db)):
    model = None
    if entity_type == "advisor": model = models.TechnicalAdvisor
    elif entity_type == "designer": model = models.Designer
    elif entity_type == "commercial": model = models.CommercialAdvisor
    elif entity_type == "sector": model = models.IndustrialSector
    elif entity_type == "machine-type": model = models.MachineType
    elif entity_type == "topic": model = models.VisitTopic
    elif entity_type == "formado": model = models.FormadoType
    elif entity_type == "cierre-inferior": model = models.InferiorClosure
    elif entity_type == "client-name": model = models.ClientName
    elif entity_type == "plant-name": model = models.PlantName
    elif entity_type == "visit-type": model = models.VisitType
    elif entity_type == "distributor-plant": model = models.DistributorPlant

    if model:
        item = db.query(model).filter(model.id == item_id).first()
        if item:
            item.name = name
            db.commit()
    return RedirectResponse(url="/configuracion", status_code=303)
