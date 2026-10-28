import logging

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import User
from services import permisos
from templating import templates
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


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, 'login.html', {"request": request, "active_page": "login"})


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
        return templates.TemplateResponse(request, 'login.html', {
            "request": request,
            "active_page": "login",
            "error": "Credenciales inválidas",
        })

    if not user.is_active:
        return templates.TemplateResponse(request, 'login.html', {
            "request": request,
            "active_page": "login",
            "error": "Cuenta desactivada",
        })

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
    return templates.TemplateResponse(request, 'register.html', {
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
        return templates.TemplateResponse(request, 'register.html', {
            "request": request,
            "active_page": "register",
            "csrf_token": generate_csrf_token(int(admin.id)),
            "error": "El nombre de usuario ya existe",
        })

    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(request, 'register.html', {
            "request": request,
            "active_page": "register",
            "csrf_token": generate_csrf_token(int(admin.id)),
            "error": "El correo electrónico ya está registrado",
        })

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

    return templates.TemplateResponse(request, 'register.html', {
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


@router.get("/usuarios/exportar-excel")
async def exportar_usuarios_excel(request: Request, db: Session = Depends(get_db)):
    """Exporta el listado de usuarios a Excel.

    No incluye contraseñas ni hashes: sólo los datos de la ficha.
    """
    from services.excel import hoja_excel, nombre_con_fecha

    usuarios = db.query(User).order_by(User.username).all()
    filas = [[
        u.username, u.full_name, u.email, u.phone, u.role,
        "Sí" if u.is_active else "No",
        u.created_at.strftime("%d/%m/%Y") if u.created_at else "",
    ] for u in usuarios]

    return hoja_excel(
        "Usuarios",
        ["Usuario", "Nombre completo", "Correo", "Teléfono", "Rol", "Activo", "Alta"],
        filas,
        nombre_con_fecha("usuarios"),
    )


@router.get("/usuarios", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request)
    users = db.query(User).order_by(User.username).all()
    csrf = generate_csrf_token(int(admin.id))
    return templates.TemplateResponse(request, 'usuarios.html', {
        "request": request,
        "active_page": "usuarios",
        "users": users,
        "csrf_token": csrf,
        "total_modulos": len(permisos.claves_asignables()),
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
    return templates.TemplateResponse(request, 'perfil.html', {
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
        return templates.TemplateResponse(request, 'perfil.html', {
            "request": request,
            "active_page": "perfil",
            "profile_user": user,
            "csrf_token": generate_csrf_token(user.id),
            "error": "El correo ya está en uso",
        })

    user.full_name = full_name
    user.email = email
    user.phone = phone
    db.commit()

    return templates.TemplateResponse(request, 'perfil.html', {
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
        return templates.TemplateResponse(request, 'perfil.html', {
            "request": request,
            "active_page": "perfil",
            "profile_user": user,
            "csrf_token": generate_csrf_token(user.id),
            "error": "La contraseña actual no es correcta",
        })

    user.hashed_password = hash_password(new_password)
    db.commit()

    return templates.TemplateResponse(request, 'perfil.html', {
        "request": request,
        "active_page": "perfil",
        "profile_user": user,
        "csrf_token": generate_csrf_token(user.id),
        "success": "Contraseña actualizada correctamente",
    })


# ── Editar un usuario ───────────────────────────────────────────────────────
#
# Antes sólo se podía crear, activar/desactivar y resetear la contraseña: para
# corregir un nombre mal escrito o cambiar un correo había que crear otro usuario.
# Y no había forma de elegir qué veía cada uno: todos veían todo el menú.

def _usuario_o_404(db: Session, user_id: int) -> User:
    objetivo = db.query(User).filter(User.id == user_id).first()
    if not objetivo:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return objetivo


def _verificar_csrf(csrf_token: str, admin: User) -> None:
    if not verify_csrf_token(csrf_token, int(admin.id)):
        raise HTTPException(status_code=403, detail="CSRF inválido")


def _normalizar_modulos(marcados) -> list:
    """Deja sólo las claves que existen y que se pueden asignar.

    La pantalla manda lo que el administrador marcó, pero el formulario se puede
    armar a mano: sin este filtro se podría guardar «usuarios» y que un usuario
    común se diera permisos a sí mismo.
    """
    return sorted(set(marcados or []) & permisos.claves_asignables())


@router.get("/usuarios/{user_id}/editar", response_class=HTMLResponse)
async def edit_user_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request)
    objetivo = _usuario_o_404(db, user_id)

    return templates.TemplateResponse(request, 'editar_usuario.html', {
        "request": request,
        "active_page": "usuarios",
        "objetivo": objetivo,
        "csrf_token": generate_csrf_token(int(admin.id)),
        "es_uno_mismo": objetivo.id == int(admin.id),
        # `None` es «sin configurar»: ve todo lo que no sea de administración, y
        # además todo lo que se agregue más adelante.
        "ve_todo": objetivo.modulos is None,
        "grupos": permisos.agrupados_para_elegir(objetivo),
        "total_modulos": len(permisos.claves_asignables()),
    })


@router.post("/usuarios/{user_id}/editar")
async def edit_user(
    request: Request,
    user_id: int,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(""),
    phone: str = Form(""),
    role: str = Form("user"),
    ve_todo: str = Form(None),
    modulos: List[str] = Form([]),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = require_admin(request)
    _verificar_csrf(csrf_token, admin)
    objetivo = _usuario_o_404(db, user_id)

    username = username.strip()
    email = email.strip()
    errores = {}

    if not username:
        errores["username"] = "El nombre de usuario no puede quedar vacío"
    elif db.query(User).filter(User.username == username,
                               User.id != objetivo.id).first():
        errores["username"] = "Ya hay otro usuario con ese nombre"

    if not email:
        errores["email"] = "El correo no puede quedar vacío"
    elif db.query(User).filter(User.email == email, User.id != objetivo.id).first():
        errores["email"] = "Ya hay otro usuario con ese correo"

    # Un administrador no se puede sacar el rol a sí mismo: se quedaría sin poder
    # volver a entrar a esta pantalla, y no hay forma de arreglarlo desde la
    # aplicación.
    es_uno_mismo = objetivo.id == int(admin.id)
    if es_uno_mismo and role != "admin":
        errores["role"] = ("No podés quitarte el rol de administrador a vos mismo. "
                           "Pedile a otro administrador que lo haga.")

    if errores:
        return templates.TemplateResponse(request, 'editar_usuario.html', {
            "request": request,
            "active_page": "usuarios",
            "objetivo": objetivo,
            "csrf_token": generate_csrf_token(int(admin.id)),
            "es_uno_mismo": es_uno_mismo,
            "ve_todo": bool(ve_todo),
            "grupos": permisos.agrupados_para_elegir(objetivo),
            "total_modulos": len(permisos.claves_asignables()),
            "errores": errores,
            # Lo que el administrador escribió, para no perderlo al volver.
            "borrador": {"username": username, "email": email,
                         "full_name": full_name, "phone": phone, "role": role,
                         "modulos": modulos},
        })

    objetivo.username = username
    objetivo.email = email
    objetivo.full_name = full_name.strip()
    objetivo.phone = phone.strip()
    objetivo.role = role if role in ("admin", "user") else "user"

    if objetivo.role == "admin":
        # Un administrador ve todo por definición: guardar una lista sería una
        # restricción que no se aplica, y confunde al leerla.
        objetivo.modulos = None
    elif ve_todo:
        objetivo.modulos = None
    else:
        objetivo.modulos = _normalizar_modulos(modulos)

    db.commit()
    logger.info("usuario %s editado por %s (rol=%s, modulos=%s)",
                objetivo.username, admin.username, objetivo.role,
                objetivo.modulos)

    return RedirectResponse(url=f"/auth/usuarios?editado={objetivo.username}",
                            status_code=303)
