from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import hash_password, verify_password, create_access_token, create_reset_token, decode_reset_token, get_current_user_optional
from app.email_utils import send_reset_email
from app.config import BASE_URL
from app.templates_config import create_templates

router = APIRouter()
templates = create_templates()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db),
                user=Depends(get_current_user_optional)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@router.get("/info", response_class=HTMLResponse)
async def info_page(request: Request, user=Depends(get_current_user_optional)):
    return templates.TemplateResponse("info.html", {"request": request, "user": user})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user=Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/ticket", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None, "user": None})


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        # Allow claiming a pre-created account (admin-added role OR HelloAsso stub)
        # by setting name and password on first registration.
        is_precreated = existing.is_bartender or existing.is_scanner or existing.is_sub_admin
        is_helloasso_stub = existing.ticket_purchased and not existing.is_admin
        if is_precreated or is_helloasso_stub:
            existing.name = name.strip()
            existing.password_hash = hash_password(password)
            db.commit()
            db.refresh(existing)
            response = RedirectResponse("/ticket", status_code=302)
            token = create_access_token(existing.id)
            response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
            return response
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Un compte existe d\u00e9j\u00e0 avec cet email. Connectez-vous ou r\u00e9initialisez votre mot de passe.", "user": None},
            status_code=400,
        )
    user = models.User(name=name.strip(), email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    response = RedirectResponse("/ticket", status_code=302)
    token = create_access_token(user.id)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/ticket", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "user": None})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password.", "user": None},
            status_code=401,
        )
    response = RedirectResponse("/ticket", status_code=302)
    token = create_access_token(user.id)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
    return response


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request, "message": None, "error": None, "user": None})


@router.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email).first()
    # Always show the same message to prevent email enumeration
    success_msg = "Si un compte existe avec cet email, vous recevrez un lien de r\u00e9initialisation."
    if user:
        token = create_reset_token(user.id)
        reset_link = f"{BASE_URL}/reset-password?token={token}"
        send_reset_email(user.email, user.name, reset_link)
    return templates.TemplateResponse("forgot_password.html", {
        "request": request, "message": success_msg, "error": None, "user": None,
    })


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    if not token:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "error": "Lien invalide.", "token": "", "success": False, "user": None,
        })
    # Verify token is valid (don't consume it yet)
    user_id = decode_reset_token(token)
    if not user_id:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "error": "Ce lien a expir\u00e9 ou est invalide. Demandez un nouveau lien.", "token": "", "success": False, "user": None,
        })
    return templates.TemplateResponse("reset_password.html", {
        "request": request, "error": None, "token": token, "success": False, "user": None,
    })


@router.post("/reset-password", response_class=HTMLResponse)
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user_id = decode_reset_token(token)
    if not user_id:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "error": "Ce lien a expir\u00e9 ou est invalide. Demandez un nouveau lien.", "token": "", "success": False, "user": None,
        })
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "error": "Utilisateur introuvable.", "token": "", "success": False, "user": None,
        })
    user.password_hash = hash_password(password)
    db.commit()
    return templates.TemplateResponse("reset_password.html", {
        "request": request, "error": None, "token": "", "success": True, "user": None,
    })


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response
