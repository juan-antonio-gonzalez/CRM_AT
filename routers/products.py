from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import models
from database import get_db
from services import product_service, pagination as pg
from templating import templates

router = APIRouter(tags=["products"])


def _product_filters(db: Session, q=None, material=None, status=None):
    """Consulta de productos con los filtros del listado.

    La comparten el listado y la exportación, para que exportar respete lo mismo
    que se ve en pantalla.
    """
    query = db.query(models.Product)
    if q:
        query = query.filter(
            (models.Product.name.ilike(f"%{q}%")) |
            (models.Product.et_number.ilike(f"%{q}%")) |
            (models.Product.material.ilike(f"%{q}%"))
        )
    if material and material != "Todos":
        query = query.filter(models.Product.material == material)
    if status and status != "Todos":
        query = query.filter(models.Product.status == status)
    return query


@router.get("/productos/exportar-excel")
async def exportar_productos_excel(
    q: Optional[str] = Query(None),
    material: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Exporta el listado filtrado de productos a Excel."""
    from services.excel import hoja_excel, nombre_con_fecha

    productos = (
        _product_filters(db, q=q, material=material, status=status)
        .order_by(models.Product.name)
        .all()
    )

    filas = []
    for p in productos:
        medidas = " x ".join(
            str(v) for v in (p.dimensions_l, p.dimensions_a, p.dimensions_h)
            if v not in (None, "")
        )
        filas.append([
            p.name, p.et_number, p.material, p.manufacturing_route, medidas,
            p.status, p.last_modified,
        ])

    return hoja_excel(
        "Productos",
        ["Nombre", "Nº ET", "Material", "Ruta de fabricación", "Medidas (L x A x H)",
         "Estado", "Última modificación"],
        filas,
        nombre_con_fecha("productos"),
    )


@router.get("/productos", response_class=HTMLResponse)
async def list_products(
    request: Request,
    q: Optional[str] = Query(None),
    material: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = _product_filters(db, q=q, material=material, status=status)

    total = query.count()
    page, per_page, offset = pg.paginate(page, per_page)
    products = query.order_by(models.Product.name).offset(offset).limit(per_page).all()

    return templates.TemplateResponse(request, 'productos.html', {
        "request": request,
        "products": products,
        "pagination": pg.build_pagination(page, per_page, total),
        "q": q, "selected_material": material, "selected_status": status,
        "active_page": "productos"
    })


@router.get("/nuevo-producto", response_class=HTMLResponse)
async def new_product_form(request: Request):
    return templates.TemplateResponse(request, 'nuevo_producto.html', {"request": request, "active_page": "productos"})


@router.post("/nuevo-producto")
async def create_product(
    name: str = Form(...),
    et_number: str = Form(...),
    material: str = Form(...),
    manufacturing_route: str = Form(""),
    dimensions_l: int = Form(0),
    dimensions_a: int = Form(0),
    dimensions_h: int = Form(0),
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    product_service.create_product(db, name, et_number, material, manufacturing_route,
                                    dimensions_l, dimensions_a, dimensions_h, status)
    return RedirectResponse(url="/productos", status_code=303)


@router.get("/editar-producto/{product_id}", response_class=HTMLResponse)
async def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = product_service.get_product(db, product_id)
    return templates.TemplateResponse(request, 'editar_producto.html', {"request": request, "product": product, "active_page": "productos"})


@router.post("/editar-producto/{product_id}")
async def update_product(
    product_id: int,
    name: str = Form(...), et_number: str = Form(...), material: str = Form(...),
    manufacturing_route: str = Form(...),
    dimensions_l: int = Form(...), dimensions_a: int = Form(...), dimensions_h: int = Form(...),
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    product_service.update_product(db, product_id, name, et_number, material,
                                    manufacturing_route, dimensions_l, dimensions_a, dimensions_h, status)
    return RedirectResponse(url="/productos", status_code=303)


@router.post("/eliminar-producto/{product_id}")
async def delete_product(product_id: int, request: Request, db: Session = Depends(get_db)):
    user = getattr(request.state, 'user', None)
    uid = int(user["sub"]) if user else None
    uname = user.get("username") if user else None
    product_service.delete_product(db, product_id, uid, uname)
    return RedirectResponse(url="/productos", status_code=303)


@router.get("/api/productos/search")
async def search_productos(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    productos = product_service.search_products(db, q)
    return [
        {"et_number": p.et_number, "description": p.name, "material": p.material}
        for p in productos
    ]


@router.get("/api/productos/{et_number}")
async def get_producto(et_number: str, db: Session = Depends(get_db)):
    producto = product_service.get_product_by_et(db, et_number)
    return {
        "et_number": producto.et_number,
        "description": producto.name,
        "material": producto.material
    }


@router.post("/api/productos/crear")
async def create_producto(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    et_number = data.get("et_number")
    if not et_number:
        raise HTTPException(status_code=400, detail="Número de ET es requerido")
    return product_service.create_product_api(db, et_number, data.get("description", ""), data.get("material", ""))
