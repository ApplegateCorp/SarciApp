from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.database import get_db
from app import models
from app.auth import (
    require_admin, require_admin_or_sub, require_bartender_or_admin,
    require_scanner_or_admin, get_current_user_optional, verify_password,
    create_access_token,
)
from app.config import ADMIN_PASSWORD
from app.qr_utils import generate_qr_base64

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


# ── Admin login ──────────────────────────────────────────────────────────────

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
    user = db.query(models.User).filter(
        models.User.email == email,
        (models.User.is_admin == True) | (models.User.is_sub_admin == True),
    ).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "admin/login.html",
            {"request": request, "error": "Identifiants admin invalides."},
            status_code=401,
        )
    response = RedirectResponse("/admin/dashboard", status_code=302)
    token = create_access_token(user.id)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24)
    return response


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    total_users = db.query(models.User).filter(models.User.is_admin == False).count()
    ticket_count = db.query(models.User).filter(models.User.ticket_purchased == True).count()
    scanned_count = db.query(models.User).filter(models.User.ticket_scanned == True).count()

    # Revenue stats
    ticket_revenue = db.query(func.coalesce(func.sum(models.Transaction.amount_cents), 0)).filter(
        models.Transaction.type == "ticket"
    ).scalar()
    bar_revenue = db.query(func.coalesce(func.sum(models.Transaction.amount_cents), 0)).filter(
        models.Transaction.type == "drink"
    ).scalar()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "admin": admin,
        "total_users": total_users,
        "ticket_count": ticket_count,
        "scanned_count": scanned_count,
        "ticket_revenue": ticket_revenue / 100,
        "bar_revenue": abs(bar_revenue) / 100,
    })


# ── Accounts list ────────────────────────────────────────────────────────────

@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(
    request: Request,
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
    filter: str = Query(default="all"),
    q: str = Query(default=""),
):
    query = db.query(models.User).filter(models.User.is_admin == False)

    if filter == "no_ticket":
        query = query.filter(models.User.ticket_purchased == False)
    elif filter == "has_ticket":
        query = query.filter(models.User.ticket_purchased == True)
    elif filter == "validated":
        query = query.filter(models.User.ticket_scanned == True)
    elif filter == "not_validated":
        query = query.filter(models.User.ticket_purchased == True, models.User.ticket_scanned == False)
    elif filter == "bartenders":
        query = query.filter(models.User.is_bartender == True)
    elif filter == "scanners":
        query = query.filter(models.User.is_scanner == True)
    elif filter == "sub_admins":
        query = query.filter(models.User.is_sub_admin == True)

    if q:
        query = query.filter(
            models.User.name.ilike(f"%{q}%") | models.User.email.ilike(f"%{q}%")
        )

    users = query.order_by(models.User.created_at.desc()).all()

    # Counts for filter badges
    counts = {
        "all": db.query(models.User).filter(models.User.is_admin == False).count(),
        "no_ticket": db.query(models.User).filter(models.User.is_admin == False, models.User.ticket_purchased == False).count(),
        "has_ticket": db.query(models.User).filter(models.User.ticket_purchased == True).count(),
        "validated": db.query(models.User).filter(models.User.ticket_scanned == True).count(),
        "not_validated": db.query(models.User).filter(models.User.ticket_purchased == True, models.User.ticket_scanned == False).count(),
    }

    return templates.TemplateResponse("admin/accounts.html", {
        "request": request,
        "admin": admin,
        "users": users,
        "filter": filter,
        "q": q,
        "counts": counts,
    })


# ── Account detail ───────────────────────────────────────────────────────────

@router.get("/accounts/{user_id}", response_class=HTMLResponse)
async def account_detail(
    user_id: int,
    request: Request,
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user_id)
        .order_by(models.Transaction.created_at.desc())
        .all()
    )

    qr_base64 = generate_qr_base64(user.token)

    return templates.TemplateResponse("admin/account_detail.html", {
        "request": request,
        "admin": admin,
        "account": user,
        "transactions": transactions,
        "qr_base64": qr_base64,
    })


@router.post("/accounts/{user_id}/grant-ticket")
async def grant_ticket(
    user_id: int,
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    """Grant a free ticket (pass) to a user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404)
    if not user.ticket_purchased:
        user.ticket_purchased = True
        tx = models.Transaction(
            user_id=user.id,
            amount_cents=0,
            type="ticket",
            description="Pass offert (admin)",
        )
        db.add(tx)
        db.commit()
    return RedirectResponse(f"/admin/accounts/{user_id}", status_code=302)


@router.post("/accounts/{user_id}/validate-ticket")
async def validate_ticket_from_list(
    user_id: int,
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    """Validate a ticket (entry scan) from the accounts list."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404)
    if user.ticket_purchased and not user.ticket_scanned:
        user.ticket_scanned = True
        db.commit()
    return RedirectResponse(f"/admin/accounts/{user_id}", status_code=302)


# ── Entry scan ───────────────────────────────────────────────────────────────

@router.get("/entry", response_class=HTMLResponse)
async def entry_scan_page(
    request: Request,
    user: models.User = Depends(require_scanner_or_admin),
):
    return templates.TemplateResponse("admin/scan_entry.html", {"request": request, "admin": user})


@router.get("/scan/{token}", response_class=JSONResponse)
async def scan_token(
    token: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_scanner_or_admin),
):
    target = db.query(models.User).filter(models.User.token == token).first()
    if not target:
        return JSONResponse({"ok": False, "error": "QR code inconnu."}, status_code=404)
    return JSONResponse({
        "ok": True,
        "user_id": target.id,
        "name": target.name,
        "email": target.email,
        "ticket_purchased": target.ticket_purchased,
        "ticket_scanned": target.ticket_scanned,
        "balance": target.balance_cents / 100,
    })


@router.post("/validate-entry", response_class=JSONResponse)
async def validate_entry(
    token: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_scanner_or_admin),
):
    target = db.query(models.User).filter(models.User.token == token).first()
    if not target:
        return JSONResponse({"ok": False, "error": "QR code inconnu."}, status_code=404)
    if not target.ticket_purchased:
        return JSONResponse({"ok": False, "error": "Cette personne n'a pas de billet."}, status_code=400)
    if target.ticket_scanned:
        return JSONResponse({"ok": False, "error": f"Billet d\u00e9j\u00e0 utilis\u00e9 ! ({target.name})"}, status_code=400)

    target.ticket_scanned = True
    db.commit()
    return JSONResponse({"ok": True, "message": f"Bienvenue, {target.name} !"})


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
    body = await request.json()
    token = body.get("token")
    drink_ids = body.get("drink_ids", [])

    if not token or not drink_ids:
        return JSONResponse({"ok": False, "error": "Donn\u00e9es manquantes."}, status_code=400)

    user = db.query(models.User).filter(models.User.token == token).first()
    if not user:
        return JSONResponse({"ok": False, "error": "QR code inconnu."}, status_code=404)

    # Check ticket is validated (scanned at entry)
    if not user.ticket_scanned:
        return JSONResponse({
            "ok": False,
            "error_type": "ticket_not_validated",
            "error": "Le spectateur doit valider son billet \u00e0 l'entr\u00e9e avant de pouvoir payer au bar.",
        }, status_code=400)

    drinks = db.query(models.DrinkItem).filter(
        models.DrinkItem.id.in_(drink_ids),
        models.DrinkItem.available == True,
    ).all()

    if not drinks:
        return JSONResponse({"ok": False, "error": "Aucune boisson s\u00e9lectionn\u00e9e."}, status_code=400)

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
            "error": f"Solde insuffisant. Solde : {user.balance_cents / 100:.2f}\u20ac, Total : {total_cents / 100:.2f}\u20ac",
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
        "message": f"{total_cents / 100:.2f}\u20ac d\u00e9bit\u00e9 \u00e0 {user.name}.",
        "new_balance": user.balance_cents / 100,
        "description": ", ".join(description_parts),
    })


# ── Drinks management ────────────────────────────────────────────────────────

@router.get("/drinks", response_class=HTMLResponse)
async def drinks_page(
    request: Request,
    admin: models.User = Depends(require_admin_or_sub),
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
    emoji: str = Form(default="\U0001f37a"),
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    drink = models.DrinkItem(name=name.strip(), price_cents=int(price * 100), emoji=emoji)
    db.add(drink)
    db.commit()
    return RedirectResponse("/admin/drinks", status_code=302)


@router.post("/drinks/{drink_id}/toggle")
async def toggle_drink(
    drink_id: int,
    admin: models.User = Depends(require_admin_or_sub),
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
    emoji: str = Form(default="\U0001f37a"),
    admin: models.User = Depends(require_admin_or_sub),
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
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    drink = db.query(models.DrinkItem).filter(models.DrinkItem.id == drink_id).first()
    if drink:
        db.delete(drink)
        db.commit()
    return RedirectResponse("/admin/drinks", status_code=302)


# ── Role management (bartenders, scanners, sub-admins) ───────────────────────

def _manage_role_page(role_name, flag_attr, template, request, admin, db):
    users = db.query(models.User).filter(getattr(models.User, flag_attr) == True).all()
    return templates.TemplateResponse(template, {
        "request": request,
        "admin": admin,
        "role_users": users,
    })


def _add_role(email_raw, name_raw, flag_attr, db):
    from app.auth import hash_password
    import secrets
    email = email_raw.lower().strip()
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        setattr(user, flag_attr, True)
        if not user.name or user.name == "":
            user.name = name_raw.strip()
        db.commit()
    else:
        user = models.User(
            name=name_raw.strip(),
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(16)),
            **{flag_attr: True},
        )
        db.add(user)
        db.commit()


def _remove_role(user_id, flag_attr, db):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        setattr(user, flag_attr, False)
        db.commit()


# ── Bartenders ──

@router.get("/bartenders", response_class=HTMLResponse)
async def bartenders_page(request: Request, admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    return _manage_role_page("barman", "is_bartender", "admin/bartenders.html", request, admin, db)


@router.post("/bartenders/add")
async def add_bartender(name: str = Form(...), email: str = Form(...),
                        admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    _add_role(email, name, "is_bartender", db)
    return RedirectResponse("/admin/bartenders", status_code=302)


@router.post("/bartenders/{user_id}/remove")
async def remove_bartender(user_id: int, admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    _remove_role(user_id, "is_bartender", db)
    return RedirectResponse("/admin/bartenders", status_code=302)


# ── Scanners ──

@router.get("/scanners", response_class=HTMLResponse)
async def scanners_page(request: Request, admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    users = db.query(models.User).filter(models.User.is_scanner == True).all()
    return templates.TemplateResponse("admin/scanners.html", {
        "request": request, "admin": admin, "role_users": users,
    })


@router.post("/scanners/add")
async def add_scanner(name: str = Form(...), email: str = Form(...),
                      admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    _add_role(email, name, "is_scanner", db)
    return RedirectResponse("/admin/scanners", status_code=302)


@router.post("/scanners/{user_id}/remove")
async def remove_scanner(user_id: int, admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    _remove_role(user_id, "is_scanner", db)
    return RedirectResponse("/admin/scanners", status_code=302)


# ── Sub-admins ──

@router.get("/sub-admins", response_class=HTMLResponse)
async def sub_admins_page(request: Request, admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    users = db.query(models.User).filter(models.User.is_sub_admin == True).all()
    return templates.TemplateResponse("admin/sub_admins.html", {
        "request": request, "admin": admin, "role_users": users,
    })


@router.post("/sub-admins/add")
async def add_sub_admin(name: str = Form(...), email: str = Form(...),
                        admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    _add_role(email, name, "is_sub_admin", db)
    return RedirectResponse("/admin/sub-admins", status_code=302)


@router.post("/sub-admins/{user_id}/remove")
async def remove_sub_admin(user_id: int, admin=Depends(require_admin_or_sub), db=Depends(get_db)):
    _remove_role(user_id, "is_sub_admin", db)
    return RedirectResponse("/admin/sub-admins", status_code=302)


# ── Analytics ────────────────────────────────────────────────────────────────

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("admin/analytics.html", {
        "request": request,
        "admin": admin,
    })


@router.get("/analytics/data", response_class=JSONResponse)
async def analytics_data(
    admin: models.User = Depends(require_admin_or_sub),
    db: Session = Depends(get_db),
):
    """Return all analytics data as JSON for charts."""
    # Drink sales breakdown
    drink_sales = (
        db.query(models.Transaction)
        .filter(models.Transaction.type == "drink")
        .all()
    )
    drink_counts: dict[str, int] = {}
    drink_revenue: dict[str, int] = {}
    for tx in drink_sales:
        for part in tx.description.split(", "):
            if "x " in part:
                qty_str, name = part.split("x ", 1)
                qty = int(qty_str.strip())
                drink_counts[name] = drink_counts.get(name, 0) + qty
                # We can't get exact price per drink from tx, so use counts only
    # Get current drink prices for revenue calculation
    drinks = db.query(models.DrinkItem).all()
    drink_price_map = {d.name: d.price_cents for d in drinks}
    for name, count in drink_counts.items():
        price = drink_price_map.get(name, 0)
        drink_revenue[name] = count * price

    # Ticket stats
    ticket_count = db.query(models.User).filter(models.User.ticket_purchased == True).count()
    ticket_validated = db.query(models.User).filter(models.User.ticket_scanned == True).count()
    ticket_revenue = db.query(func.coalesce(func.sum(models.Transaction.amount_cents), 0)).filter(
        models.Transaction.type == "ticket"
    ).scalar()
    bar_revenue_total = abs(db.query(func.coalesce(func.sum(models.Transaction.amount_cents), 0)).filter(
        models.Transaction.type == "drink"
    ).scalar())
    topup_total = db.query(func.coalesce(func.sum(models.Transaction.amount_cents), 0)).filter(
        models.Transaction.type == "topup"
    ).scalar()

    # Time series: bar revenue per hour
    bar_txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.type == "drink")
        .order_by(models.Transaction.created_at)
        .all()
    )
    bar_by_hour: dict[str, int] = {}
    for tx in bar_txs:
        hour_key = tx.created_at.strftime("%Y-%m-%d %H:00")
        bar_by_hour[hour_key] = bar_by_hour.get(hour_key, 0) + abs(tx.amount_cents)

    # Time series: ticket purchases over time
    ticket_txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.type == "ticket")
        .order_by(models.Transaction.created_at)
        .all()
    )
    tickets_by_day: dict[str, int] = {}
    for tx in ticket_txs:
        day_key = tx.created_at.strftime("%Y-%m-%d")
        tickets_by_day[day_key] = tickets_by_day.get(day_key, 0) + 1

    # Topup by hour
    topup_txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.type == "topup")
        .order_by(models.Transaction.created_at)
        .all()
    )
    topup_by_hour: dict[str, int] = {}
    for tx in topup_txs:
        hour_key = tx.created_at.strftime("%Y-%m-%d %H:00")
        topup_by_hour[hour_key] = topup_by_hour.get(hour_key, 0) + tx.amount_cents

    return JSONResponse({
        "ticket_count": ticket_count,
        "ticket_validated": ticket_validated,
        "ticket_revenue_cents": ticket_revenue,
        "bar_revenue_cents": bar_revenue_total,
        "topup_total_cents": topup_total,
        "drink_counts": drink_counts,
        "drink_revenue_cents": drink_revenue,
        "bar_by_hour": bar_by_hour,
        "tickets_by_day": tickets_by_day,
        "topup_by_hour": topup_by_hour,
    })
