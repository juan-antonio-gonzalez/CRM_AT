from pydantic import BaseModel
from typing import Optional


class ProductSearchResult(BaseModel):
    et_number: str
    description: str
    material: str


class ProductCreate(BaseModel):
    et_number: str
    description: str = ""
    material: str = ""


class ProductCreateResponse(BaseModel):
    status: str
    message: str
