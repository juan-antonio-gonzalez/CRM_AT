from pydantic import BaseModel
from typing import Optional


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    role: str = "user"


class UserLogin(BaseModel):
    username: str
    password: str
