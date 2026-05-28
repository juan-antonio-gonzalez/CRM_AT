from sqlalchemy.orm import Session
from fastapi import HTTPException
import models
from enums import ProductStatus
import datetime


def list_products(db: Session, q: str = None, material: str = None, status: str = None):
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
    return query.order_by(models.Product.name).all()


def create_product(db: Session, name: str, et_number: str, material: str,
                   manufacturing_route: str = "", dimensions_l: int = 0,
                   dimensions_a: int = 0, dimensions_h: int = 0,
                   status: str = None):
    new_product = models.Product(
        name=name, et_number=et_number, material=material,
        manufacturing_route=manufacturing_route,
        dimensions_l=dimensions_l, dimensions_a=dimensions_a, dimensions_h=dimensions_h,
        status=status or ProductStatus.ACTIVO.value, last_modified="Hoy"
    )
    db.add(new_product)
    db.commit()
    return new_product


def get_product(db: Session, product_id: int):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


def update_product(db: Session, product_id: int, name: str, et_number: str,
                   material: str, manufacturing_route: str,
                   dimensions_l: int, dimensions_a: int, dimensions_h: int,
                   status: str):
    product = get_product(db, product_id)
    product.name = name
    product.et_number = et_number
    product.material = material
    product.manufacturing_route = manufacturing_route
    product.dimensions_l = dimensions_l
    product.dimensions_a = dimensions_a
    product.dimensions_h = dimensions_h
    product.status = status
    db.commit()
    return product


def delete_product(db: Session, product_id: int, user_id: int = None, username: str = None):
    product = get_product(db, product_id)
    from services.trash_service import move_to_trash
    move_to_trash(db, "product", product_id, {
        "name": product.name, "et_number": product.et_number,
        "material": product.material,
        "manufacturing_route": product.manufacturing_route,
        "dimensions_l": product.dimensions_l,
        "dimensions_a": product.dimensions_a,
        "dimensions_h": product.dimensions_h,
        "status": product.status, "last_modified": product.last_modified,
    }, user_id, username, product.name)
    db.delete(product)
    db.commit()


def search_products(db: Session, q: str, limit: int = 10):
    return db.query(models.Product).filter(
        (models.Product.et_number.ilike(f"%{q}%")) |
        (models.Product.name.ilike(f"%{q}%"))
    ).limit(limit).all()


def get_product_by_et(db: Session, et_number: str):
    product = db.query(models.Product).filter(models.Product.et_number == et_number).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


def create_product_api(db: Session, et_number: str, description: str, material: str):
    existing = db.query(models.Product).filter(models.Product.et_number == et_number).first()
    if existing:
        return {"status": "exists", "message": "El producto ya existe en la biblioteca"}
    new_product = models.Product(
        et_number=et_number, name=description, material=material,
        last_modified=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    db.add(new_product)
    db.commit()
    return {"status": "success", "message": "Producto agregado a la biblioteca"}
