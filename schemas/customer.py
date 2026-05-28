from pydantic import BaseModel
from typing import Optional


class CustomerPlant(BaseModel):
    id: int
    name: str


class CustomerPlantLine(BaseModel):
    name: str


class CustomerMachine(BaseModel):
    id: int
    name: str
    serial: str
    line: str = ""
    status: Optional[str] = None


class CustomerDetail(BaseModel):
    name: str
    plant: Optional[str] = None
    industry_sector: Optional[str] = None
    technical_advisor: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    observations: Optional[str] = None


class KpiAssignment(BaseModel):
    id: int
    cliente: str
    at: str = "No asignado"
    estandar: int = 0
    premium: int = 0
    total: int = 0
    attention_required: bool = False
    attention_observations: str = ""


class KpiAssignmentCreate(BaseModel):
    name: str
    at: Optional[str] = None


class KpiAssignmentUpdate(BaseModel):
    standard: Optional[int] = None
    premium: Optional[int] = None
    at: Optional[str] = None
    name: Optional[str] = None
    attention_required: Optional[bool] = None
    attention_observations: Optional[str] = None
