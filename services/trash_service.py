from sqlalchemy.orm import Session
from typing import Optional
import models
from sqlalchemy import desc
import datetime


def move_to_trash(
    db: Session,
    entity_type: str,
    entity_id: Optional[int],
    entity_data: dict,
    deleted_by_id: Optional[int] = None,
    deleted_by_name: Optional[str] = None,
    entity_name: Optional[str] = None,
):
    item = models.TrashItem(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        data=entity_data,
        deleted_by=deleted_by_id,
        deleted_by_name=deleted_by_name,
    )
    db.add(item)
    db.commit()


def list_trash(db: Session, entity_type: Optional[str] = None):
    query = db.query(models.TrashItem).filter(models.TrashItem.restored_at == None)
    if entity_type:
        query = query.filter(models.TrashItem.entity_type == entity_type)
    return query.order_by(desc(models.TrashItem.deleted_at)).all()


def restore_from_trash(db: Session, trash_id: int, restored_by_id: int):
    item = db.query(models.TrashItem).filter(models.TrashItem.id == trash_id).first()
    if not item:
        return None
    item.restored_at = datetime.datetime.now(datetime.UTC)
    item.restored_by = restored_by_id
    db.commit()
    return item
