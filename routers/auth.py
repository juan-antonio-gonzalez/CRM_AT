from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User
from security import (
    hash_password,
    verify_password,
    create_token,
    COOKIE_NAME,
    get_current_user,
    generate_csrf_token,
    verify_csrf_token,
)


def require_admin(request: Request) -> User:
    from database import SessionLocal
    user_data = get_current_user(request)
    if not user_data or user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_data["sub"])).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="Acceso denegado")
        return user
    finally:
        db.close()


router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "active_page": "login"})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        (User.username == username) | (User.email == username)
    ).first()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "active_page": "login",
            "error": "Credenciales inválidas",
        }, status_code=401)

    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "active_page": "login",
            "error": "Cuenta desactivada",
        }, status_code=403)

    token = create_token({"sub": str(user.id), "username": user.username, "role": user.role})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
        secure=False,
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    require_admin(request)
    csrf = generate_csrf_token(int(get_current_user(request)["sub"]))
    return templates.TemplateResponse("register.html", {
        "request": request,
        "active_page": "register",
        "csrf_token": csrf,
    })


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)

    if not verify_csrf_token(csrf_token, int(admin.id)):
        raise HTTPException(status_code=403, detail="CSRF inválido")

    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("register.html", {
            "request": request,
            "active_page": "register",
            "csrf_token": generate_csrf_token(int(admin.id)),
            "error": "El nombre de usuario ya existe",
        }, status_code=400)

    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("register.html", {
            "request": request,
            "active_page": "register",
            "csrf_token": generate_csrf_token(int(admin.id)),
            "error": "El correo electrónico ya está registrado",
        }, status_code=400)

    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role if role in ("admin", "user") else "user",
        is_active=True,
    )
    db.add(user)
    db.commit()

    return templates.TemplateResponse("register.html", {
        "request": request,
        "active_page": "register",
        "csrf_token": generate_csrf_token(int(admin.id)),
        "success": f"Usuario '{username}' creado correctamente",
    })


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response


@router.get("/usuarios", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request)
    users = db.query(User).order_by(User.username).all()
    csrf = generate_csrf_token(int(admin.id))
    return templates.TemplateResponse("usuarios.html", {
        "request": request,
        "active_page": "usuarios",
        "users": users,
        "csrf_token": csrf,
    })


@router.post("/usuarios/{user_id}/toggle")
async def toggle_user(
    request: Request,
    user_id: int,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    if not verify_csrf_token(csrf_token, int(admin.id)):
        raise HTTPException(status_code=403, detail="CSRF inválido")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if target.id == int(admin.id):
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")

    target.is_active = not target.is_active
    db.commit()
    return RedirectResponse(url="/auth/usuarios", status_code=303)


@router.post("/usuarios/{user_id}/reset-password")
async def reset_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    if not verify_csrf_token(csrf_token, int(admin.id)):
        raise HTTPException(status_code=403, detail="CSRF inválido")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    target.hashed_password = hash_password(new_password)
    db.commit()
    return RedirectResponse(url="/auth/usuarios", status_code=303)


@router.get("/perfil", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user_data = get_current_user(request)
    if not user_data:
        return RedirectResponse(url="/auth/login", status_code=303)

    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    csrf_token = generate_csrf_token(user.id)
    return templates.TemplateResponse("perfil.html", {
        "request": request,
        "active_page": "perfil",
        "profile_user": user,
        "csrf_token": csrf_token,
    })


@router.post("/perfil")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user_data = get_current_user(request)
    if not user_data:
        return RedirectResponse(url="/auth/login", status_code=303)

    if not verify_csrf_token(csrf_token, int(user_data["sub"])):
        raise HTTPException(status_code=403, detail="CSRF inválido")

    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    if email != user.email and db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("perfil.html", {
            "request": request,
            "active_page": "perfil",
            "profile_user": user,
            "csrf_token": generate_csrf_token(user.id),
            "error": "El correo ya está en uso",
        }, status_code=400)

    user.full_name = full_name
    user.email = email
    user.phone = phone
    db.commit()

    return templates.TemplateResponse("perfil.html", {
        "request": request,
        "active_page": "perfil",
        "profile_user": user,
        "csrf_token": generate_csrf_token(user.id),
        "success": "Perfil actualizado correctamente",
    })


@router.post("/perfil/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    user_data = get_current_user(request)
    if not user_data:
        return RedirectResponse(url="/auth/login", status_code=303)

    if not verify_csrf_token(csrf_token, int(user_data["sub"])):
        raise HTTPException(status_code=403, detail="CSRF inválido")

    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)

    if not verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse("perfil.html", {
            "request": request,
            "active_page": "perfil",
            "profile_user": user,
            "csrf_token": generate_csrf_token(user.id),
            "error": "La contraseña actual no es correcta",
        }, status_code=400)

    user.hashed_password = hash_password(new_password)
    db.commit()

    return templates.TemplateResponse("perfil.html", {
        "request": request,
        "active_page": "perfil",
        "profile_user": user,
        "csrf_token": generate_csrf_token(user.id),
        "success": "Contraseña actualizada correctamente",
    })
