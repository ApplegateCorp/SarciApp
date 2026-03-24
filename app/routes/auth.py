from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import hash_password, verify_password, create_access_token, get_current_user_optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


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
        # If the account was pre-created by admin (bartender), let them claim it
        if existing.is_bartender and not existing.ticket_purchased:
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
            {"request": request, "error": "Un compte existe d\u00e9j\u00e0 avec cet email."},
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
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


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
            {"request": request, "error": "Invalid email or password."},
            status_code=401,
        )
    response = RedirectResponse("/ticket", status_code=302)
    token = create_access_token(user.id)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response
