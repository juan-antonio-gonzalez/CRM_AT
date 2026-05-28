from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
import models
from database import get_db
from enums import RelevamientoStatus, VisitStatus
import datetime
import json

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total_customers = db.query(models.Customer).count()
    total_visits = db.query(models.TechnicalVisit).count()

    today = datetime.datetime.now(datetime.UTC)
    six_months_ago = today - datetime.timedelta(days=180)

    visit_stats = db.query(
        func.count(models.TechnicalVisit.id).filter(models.TechnicalVisit.date >= six_months_ago).label('total_recent'),
        func.count(models.TechnicalVisit.id).filter(
            models.TechnicalVisit.date >= six_months_ago,
            models.TechnicalVisit.status == VisitStatus.FINALIZADA.value
        ).label('completed_recent'),
    ).first()

    total_machines = db.query(models.Machine).count()
    completed_surveys = db.query(models.Machine).filter(
        models.Machine.relevamiento_status == RelevamientoStatus.COMPLETADO.value
    ).count()
    survey_progress = (completed_surveys / total_machines * 100) if total_machines > 0 else 0

    # Fetch raw dates and group in Python for cross-DB compatibility
    recent_visits = db.query(models.TechnicalVisit.date).filter(
        models.TechnicalVisit.date >= six_months_ago
    ).all()
    visits_by_month_map = {}
    for (d,) in recent_visits:
        if d:
            key = d.strftime("%Y-%m")
            visits_by_month_map[key] = visits_by_month_map.get(key, 0) + 1

    chart_months_labels = []
    chart_visits_data = []
    for i in range(5, -1, -1):
        month_date = today.replace(day=1) - datetime.timedelta(days=i*30)
        month_key = month_date.strftime("%Y-%m")
        chart_months_labels.append(month_date.strftime("%b %y"))
        chart_visits_data.append(visits_by_month_map.get(month_key, 0))

    visit_types_raw = db.query(
        models.TechnicalVisit.visit_type,
        func.count(models.TechnicalVisit.id)
    ).group_by(models.TechnicalVisit.visit_type).all()
    visit_types_labels = [vt[0] or "Otros" for vt in visit_types_raw]
    visit_types_data = [vt[1] for vt in visit_types_raw]

    all_visits = db.query(models.TechnicalVisit.topics).all()
    topics_count = {}
    for v_topics in all_visits:
        topics_list = v_topics[0]
        if topics_list and isinstance(topics_list, list):
            for t in topics_list:
                topics_count[t] = topics_count.get(t, 0) + 1
        elif topics_list and isinstance(topics_list, str):
            try:
                t_list = json.loads(topics_list)
                for t in t_list:
                    topics_count[t] = topics_count.get(t, 0) + 1
            except:
                topics_count[topics_list] = topics_count.get(topics_list, 0) + 1

    sorted_topics = sorted(topics_count.items(), key=lambda x: x[1], reverse=True)[:5]
    chart_topics_labels = [t[0] for t in sorted_topics]
    chart_topics_data = [t[1] for t in sorted_topics]

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "stats": {
            "total_customers": total_customers,
            "total_visits": total_visits,
            "completed_visits": visit_stats.completed_recent if visit_stats else 0,
            "survey_progress": round(survey_progress, 1),
            "total_machines": total_machines
        },
        "charts": {
            "months": chart_months_labels,
            "visits_data": chart_visits_data,
            "visit_types_labels": visit_types_labels,
            "visit_types_data": visit_types_data,
            "topics_labels": chart_topics_labels,
            "topics_data": chart_topics_data
        }
    })


@router.get("/search", response_class=HTMLResponse)
async def global_search(request: Request, q: str = Query(...), db: Session = Depends(get_db)):
    customers = db.query(models.Customer).filter(
        (models.Customer.name.ilike(f"%{q}%")) |
        (models.Customer.plant.ilike(f"%{q}%"))
    ).limit(5).all()

    products = db.query(models.Product).filter(
        (models.Product.name.ilike(f"%{q}%")) |
        (models.Product.et_number.ilike(f"%{q}%"))
    ).limit(5).all()

    machines = db.query(models.Machine).filter(
        (models.Machine.serial_number.ilike(f"%{q}%")) |
        (models.Machine.model.ilike(f"%{q}%"))
    ).limit(5).all()

    return templates.TemplateResponse("layout.html", {
        "request": request,
        "search_results": {
            "customers": customers,
            "products": products,
            "machines": machines
        },
        "search_query": q,
        "active_page": "dashboard"
    })
