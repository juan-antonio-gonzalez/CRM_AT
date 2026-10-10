from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from services import kpi_service, customer_service
from templating import templates

router = APIRouter(tags=["kpis"])


@router.get("/kpis-at", response_class=HTMLResponse)
async def kpis_at(request: Request, db: Session = Depends(get_db)):
    assignments = kpi_service.list_assignments(db)
    available_customers = kpi_service.get_available_customers(db)
    advisor_names = kpi_service.get_advisor_names(db)
    table_data, grand_total_estandar, grand_total_premium = kpi_service.build_table_data(assignments)

    return templates.TemplateResponse(request, 'kpis_at.html', {
        "request": request,
        "active_page": "kpis_at",
        "table_data": table_data,
        "advisors": advisor_names,
        "customer_names": available_customers,
        "stats": {
            "total_visitas": grand_total_estandar + grand_total_premium,
            "total_premium": grand_total_premium,
            "total_estandar": grand_total_estandar
        }
    })


@router.post("/api/customers/quick-create")
async def quick_create_assignment(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    new_assignment = kpi_service.quick_create_assignment(
        db, data.get("name"), data.get("at"), data.get("status", "Activo"),
        data.get("valid_from"), data.get("valid_to")
    )
    return {
        "status": "success",
        "id": new_assignment.id,
        "cliente": new_assignment.customer_name,
        "at": new_assignment.technical_advisor or "No asignado",
        "estandar": 0,
        "premium": 0,
        "total": 0,
        "attention_required": getattr(new_assignment, 'attention_required', False),
        "attention_observations": getattr(new_assignment, 'attention_observations', ""),
        "status": getattr(new_assignment, 'status', "Activo")
    }


@router.post("/api/customers/{assignment_id}/update-kpis")
async def update_assignment_kpis(assignment_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    return kpi_service.update_assignment_kpis(db, assignment_id, data)


@router.post("/eliminar-asignacion/{assignment_id}")
async def delete_assignment(assignment_id: int, request: Request, redirect: str = Query("/kpis-at"), db: Session = Depends(get_db)):
    user = getattr(request.state, 'user', None)
    uid = int(user["sub"]) if user else None
    uname = user.get("username") if user else None
    kpi_service.delete_assignment(db, assignment_id, uid, uname)
    return RedirectResponse(url=redirect, status_code=303)


@router.get("/api/kpis-at/data")
async def kpis_at_data(request: Request, db: Session = Depends(get_db)):
    assignments = kpi_service.list_assignments(db)
    available_customers = kpi_service.get_available_customers(db)
    advisor_names = kpi_service.get_advisor_names(db)
    table_data, grand_total_estandar, grand_total_premium = kpi_service.build_table_data(assignments)
    return {
        "table_data": table_data,
        "advisors": advisor_names,
        "customer_names": available_customers,
        "stats": {
            "total_visitas": grand_total_estandar + grand_total_premium,
            "total_premium": grand_total_premium,
            "total_estandar": grand_total_estandar
        }
    }


@router.get("/api/customers/{customer_id}/details")
async def get_customer_details(customer_id: int, db: Session = Depends(get_db)):
    customer = customer_service.get_customer(db, customer_id)
    return {
        "name": customer.name,
        "plant": customer.plant,
        "industry_sector": customer.industry_sector,
        "technical_advisor": customer.technical_advisor,
        "city": customer.city,
        "address": customer.address,
        "status": customer.status,
        "observations": customer.observations
    }
