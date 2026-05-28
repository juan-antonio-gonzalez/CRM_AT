from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
COOKIE_NAME = "session"
CSRF_COOKIE = "csrf"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return decode_token(token)


async def login_required(request: Request):
    user = get_current_user(request)
    if not user:
        return None
    return user


def generate_csrf_token(user_id: int) -> str:
    data = {
        "uid": user_id,
        "type": "csrf",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(data, settings.secret_key, algorithm=ALGORITHM)


def verify_csrf_token(token: str, user_id: int) -> bool:
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return data.get("uid") == user_id and data.get("type") == "csrf"
    except JWTError:
        return False
