from pydantic import BaseModel
from typing import Optional, Any, List
from datetime import date, datetime


class VisitEvent(BaseModel):
    id: int
    title: str
    start: str
    status: str
    color: str
    description: Optional[str] = None
