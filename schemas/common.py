from pydantic import BaseModel
from typing import Optional, Any


class Message(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str


class SuccessResponse(BaseModel):
    status: str = "success"
    message: str
