import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import hash_password
from app.config import HELLOASSO_WEBHOOK_SECRET
from app.email_utils import send_welcome_email

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_ticket_type(name: str) -> str:
    """Normalize HelloAsso tier name to a simple category."""
    lower = name.lower()
    if "vendredi" in lower or "friday" in lower:
        return "1 Jour Vendredi"
    elif "samedi" in lower or "saturday" in lower:
        return "1 Jour Samedi"
    else:
        return "Pass 2 Jours"


def _extract_payer_info(payload: dict) -> tuple[str, str, list[dict]]:
    """
    Extract email, name, and ticket items from HelloAsso webhook payload.
    Returns (email, full_name, items) where items is a list of
    {"name": "Monkey Pass - 2 Jours", "amount": 9000} dicts.
    """
    data = payload.get("data", payload)
    payer = data.get("payer", {})

    email = (payer.get("email") or "").lower().strip()
    first_name = payer.get("firstName", "")
    last_name = payer.get("lastName", "")
    full_name = f"{first_name} {last_name}".strip()

    raw_items = data.get("items", [])
    items = []
    for item in raw_items:
        item_name = item.get("name", "Billet")
        item_amount = item.get("amount", 0)
        items.append({"name": item_name, "amount": item_amount})

    return email, full_name, items


@router.post("/webhooks/helloasso")
async def helloasso_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive HelloAsso order/payment notifications."""

    if HELLOASSO_WEBHOOK_SECRET:
        provided_secret = request.headers.get("x-helloasso-secret", "")
        if provided_secret != HELLOASSO_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(f"HelloAsso webhook received: {payload}")

    event_type = payload.get("eventType", "")
    if event_type and event_type not in ("Order", "Payment"):
        logger.info(f"HelloAsso webhook: skipping event type '{event_type}'")
        return JSONResponse({"ok": True, "skipped": True})

    email, full_name, items = _extract_payer_info(payload)

    if not email:
        logger.warning(f"HelloAsso webhook: no payer email found in payload")
        return JSONResponse({"ok": True, "skipped": True})

    # ── Look up or create buyer ─────────────────────────────────────────
    user = db.query(models.User).filter(models.User.email == email).first()
    has_account = user is not None

    if user:
        if user.ticket_purchased:
            logger.info(f"HelloAsso webhook: ticket already purchased for {email}")
            return JSONResponse({"ok": True, "already_purchased": True})
        user.ticket_purchased = True
        if not user.name or user.name == email:
            user.name = full_name or user.name
    else:
        user = models.User(
            name=full_name or email,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            ticket_purchased=True,
        )
        db.add(user)

    db.flush()

    # ── Process each ticket item ────────────────────────────────────────
    if not items:
        # Fallback: no items parsed, record as single ticket
        data = payload.get("data", payload)
        amount = data.get("amount", {})
        amount_cents = amount.get("total", 0) if isinstance(amount, dict) else 0
        tx = models.Transaction(
            user_id=user.id,
            amount_cents=amount_cents,
            type="ticket",
            description=_normalize_ticket_type(""),
        )
        db.add(tx)
    else:
        # First item → buyer's own ticket
        first = items[0]
        ticket_type = _normalize_ticket_type(first["name"])
        tx = models.Transaction(
            user_id=user.id,
            amount_cents=first["amount"],
            type="ticket",
            description=ticket_type,
        )
        db.add(tx)

        # Additional items → pending tickets to assign
        for item in items[1:]:
            item_type = _normalize_ticket_type(item["name"])
            # Record the transaction on the buyer for accounting
            extra_tx = models.Transaction(
                user_id=user.id,
                amount_cents=item["amount"],
                type="ticket",
                description=item_type,
            )
            db.add(extra_tx)
            # Create pending ticket for assignment
            pending = models.PendingTicket(
                buyer_id=user.id,
                ticket_type=item_type,
                amount_cents=item["amount"],
            )
            db.add(pending)

    db.commit()
    db.refresh(user)

    # ── Send welcome email ──────────────────────────────────────────────
    try:
        send_welcome_email(user.email, user.name, has_account)
    except Exception as e:
        logger.error(f"HelloAsso webhook: failed to send welcome email: {e}")

    pending_count = len(items) - 1 if len(items) > 1 else 0
    logger.info(f"HelloAsso webhook: ticket activated for {email}, {pending_count} pending tickets to assign")
    return JSONResponse({
        "ok": True, "user_id": user.id, "ticket_activated": True,
        "pending_tickets": pending_count,
    })
