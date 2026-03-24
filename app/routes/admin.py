from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import require_admin, require_bartender_or_admin, get_current_user_optional, verify_password, create_access_token
from app.config import ADMIN_PASSWORD

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


# ── Admin login (separate from user login) ──────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})


@router.post("/login")
async def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email, models.User.is_admin == True).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "admin/login.html",
            {"request": request, "error": "Invalid admin credentials."},
            status_code=401,
        )
    response = RedirectResponse("/admin/dashboard", status_code=302)
    from app.auth import create_access_token
    token = create_access_token(user.id)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24)
    return response


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(models.User).count()
    ticket_count = db.query(models.User).filter(models.User.ticket_purchased == True).count()
    scanned_count = db.query(models.User).filter(models.User.ticket_scanned == True).count()
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "admin": admin,
        "total_users": total_users,
        "ticket_count": ticket_count,
        "scanned_count": scanned_count,
    })


# ── Entry scan ───────────────────────────────────────────────────────────────

@router.get("/entry", response_class=HTMLResponse)
async def entry_scan_page(request: Request, admin: models.User = Depends(require_admin)):
    return templates.TemplateResponse("admin/scan_entry.html", {"request": request, "admin": admin})


@router.get("/scan/{token}", response_class=JSONResponse)
async def scan_token(token: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Called when admin scans a QR code. Returns attendee info."""
    user = db.query(models.User).filter(models.User.token == token).first()
    if not user:
        return JSONResponse({"ok": False, "error": "Unknown QR code."}, status_code=404)
    return JSONResponse({
        "ok": True,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "ticket_purchased": user.ticket_purchased,
        "ticket_scanned": user.ticket_scanned,
        "balance": user.balance_cents / 100,
    })


@router.post("/validate-entry", response_class=JSONResponse)
async def validate_entry(
    token: str = Form(...),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Mark a ticket as scanned (one-time entry validation)."""
    user = db.query(models.User).filter(models.User.token == token).first()
    if not user:
        return JSONResponse({"ok": False, "error": "Unknown QR code."}, status_code=404)
    if not user.ticket_purchased:
        return JSONResponse({"ok": False, "error": "This person has not purchased a ticket."}, status_code=400)
    if user.ticket_scanned:
        return JSONResponse({"ok": False, "error": f"Ticket already used! ({user.name})"}, status_code=400)

    user.ticket_scanned = True
    db.commit()
    return JSONResponse({"ok": True, "message": f"Welcome, {user.name}!"})


# ── Bar ──────────────────────────────────────────────────────────────────────

@router.get("/bar", response_class=HTMLResponse)
async def bar_page(
    request: Request,
    user: models.User = Depends(require_bartender_or_admin),
    db: Session = Depends(get_db),
):
    drinks = db.query(models.DrinkItem).filter(models.DrinkItem.available == True).all()
    return templates.TemplateResponse("admin/bar.html", {
        "request": request,
        "admin": user,
        "drinks": drinks,
    })


@router.post("/charge", response_class=JSONResponse)
async def charge(
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_bartender_or_admin),
):
    """Receive a JSON payload with token + list of drink IDs, deduct from balance."""
    body = await request.json()
    token = body.get("token")
    drink_ids = body.get("drink_ids", [])

    if not token or not drink_ids:
        return JSONResponse({"ok": False, "error": "Missing token or drinks."}, status_code=400)

    user = db.query(models.User).filter(models.User.token == token).first()
    if not user:
        return JSONResponse({"ok": False, "error": "Unknown QR code."}, status_code=404)

    drinks = db.query(models.DrinkItem).filter(
        models.DrinkItem.id.in_(drink_ids),
        models.DrinkItem.available == True,
    ).all()

    if not drinks:
        return JSONResponse({"ok": False, "error": "No valid drinks selected."}, status_code=400)

    # Build order summary
    drink_map: dict[int, int] = {}
    for did in drink_ids:
        drink_map[did] = drink_map.get(did, 0) + 1

    total_cents = 0
    description_parts = []
    for drink in drinks:
        qty = drink_map.get(drink.id, 0)
        total_cents += drink.price_cents * qty
        description_parts.append(f"{qty}x {drink.name}")

    if user.balance_cents < total_cents:
        return JSONResponse({
            "ok": False,
            "error": f"Insufficient balance. Balance: {user.balance_cents / 100:.2f}€, Total: {total_cents / 100:.2f}€",
        }, status_code=400)

    user.balance_cents -= total_cents
    transaction = models.Transaction(
        user_id=user.id,
        amount_cents=-total_cents,
        type="drink",
        description=", ".join(description_parts),
    )
    db.add(transaction)
    db.commit()

    return JSONResponse({
        "ok": True,
        "message": f"Charged {total_cents / 100:.2f}€ to {user.name}.",
        "new_balance": user.balance_cents / 100,
        "description": ", ".join(description_parts),
    })


# ── Drinks management ────────────────────────────────────────────────────────

@router.get("/drinks", response_class=HTMLResponse)
async def drinks_page(
    request: Request,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    drinks = db.query(models.DrinkItem).all()
    return templates.TemplateResponse("admin/drinks.html", {
        "request": request,
        "admin": admin,
        "drinks": drinks,
    })


@router.post("/drinks/add")
async def add_drink(
    name: str = Form(...),
    price: float = Form(...),
    emoji: str = Form(default="🍺"),
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    drink = models.DrinkItem(name=name.strip(), price_cents=int(price * 100), emoji=emoji)
    db.add(drink)
    db.commit()
    return RedirectResponse("/admin/drinks", status_code=302)


@router.post("/drinks/{drink_id}/toggle")
async def toggle_drink(
    drink_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    drink = db.query(models.DrinkItem).filter(models.DrinkItem.id == drink_id).first()
    if drink:
        drink.available = not drink.available
        db.commit()
    return RedirectResponse("/admin/drinks", status_code=302)


@router.post("/drinks/{drink_id}/edit")
async def edit_drink(
    drink_id: int,
    name: str = Form(...),
    price: float = Form(...),
    emoji: str = Form(default="🍺"),
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    drink = db.query(models.DrinkItem).filter(models.DrinkItem.id == drink_id).first()
    if drink:
        drink.name = name.strip()
        drink.price_cents = int(price * 100)
        drink.emoji = emoji
        db.commit()
    return RedirectResponse("/admin/drinks", status_code=302)


@router.post("/drinks/{drink_id}/delete")
async def delete_drink(
    drink_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    drink = db.query(models.DrinkItem).filter(models.DrinkItem.id == drink_id).first()
    if drink:
        db.delete(drink)
        db.commit()
    return RedirectResponse("/admin/drinks", status_code=302)


# ── Bartender management ─────────────────────────────────────────────────────

@router.get("/bartenders", response_class=HTMLResponse)
async def bartenders_page(
    request: Request,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    bartenders = db.query(models.User).filter(models.User.is_bartender == True).all()
    return templates.TemplateResponse("admin/bartenders.html", {
        "request": request,
        "admin": admin,
        "bartenders": bartenders,
    })


@router.post("/bartenders/add")
async def add_bartender(
    name: str = Form(...),
    email: str = Form(...),
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email = email.lower().strip()
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        # User already exists — just grant bartender role
        user.is_bartender = True
        if not user.name or user.name == "":
            user.name = name.strip()
        db.commit()
    else:
        # Create a placeholder account — bartender will set password when they register
        # For now, flag the email so when they register they auto-get bartender role
        from app.auth import hash_password
        import secrets
        user = models.User(
            name=name.strip(),
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(16)),  # temp password
            is_bartender=True,
        )
        db.add(user)
        db.commit()
    return RedirectResponse("/admin/bartenders", status_code=302)


@router.post("/bartenders/{user_id}/remove")
async def remove_bartender(
    user_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_bartender = False
        db.commit()
    return RedirectResponse("/admin/bartenders", status_code=302)
