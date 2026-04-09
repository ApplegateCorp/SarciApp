"""Customer-facing bar and scanner routes.

These serve the same functionality as the admin bar/entry pages but live
outside the /admin prefix so non-admin bartenders and scanners stay in the
customer-facing part of the site.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.auth import require_bartender_or_admin, require_scanner_or_admin
from app.templates_config import create_templates

router = APIRouter()
templates = create_templates()


# ── Bar ─────────────────────────────────────────────────────────────────────

@router.get("/bar", response_class=HTMLResponse)
async def bar_page(
    request: Request,
    user: models.User = Depends(require_bartender_or_admin),
    db: Session = Depends(get_db),
):
    drinks = db.query(models.DrinkItem).filter(models.DrinkItem.available == True).all()
    return templates.TemplateResponse("bar.html", {
        "request": request,
        "user": user,
        "drinks": drinks,
    })


@router.post("/bar/charge", response_class=JSONResponse)
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


# ── Scanner ─────────────────────────────────────────────────────────────────

@router.get("/scanner", response_class=HTMLResponse)
async def scanner_page(
    request: Request,
    user: models.User = Depends(require_scanner_or_admin),
):
    return templates.TemplateResponse("scan_entry.html", {"request": request, "user": user})


@router.post("/scanner/validate-entry", response_class=JSONResponse)
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
