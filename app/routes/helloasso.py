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


@router.post("/webhooks/helloasso")
async def helloasso_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive HelloAsso order notifications.

    HelloAsso sends a POST with JSON body when an order is completed.
    Payload structure:
    {
      "eventType": "Order",
      "data": {
        "payer": {
          "email": "...",
          "firstName": "...",
          "lastName": "..."
        },
        "items": [...],
        "amount": { "total": 1500 },
        ...
      }
    }
    """
    # ── Verify shared secret ────────────────────────────────────────────
    if HELLOASSO_WEBHOOK_SECRET:
        provided_secret = request.headers.get("x-helloasso-secret", "")
        if provided_secret != HELLOASSO_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = payload.get("eventType", "")
    if event_type != "Order":
        return JSONResponse({"ok": True, "skipped": True})

    data = payload.get("data", {})
    payer = data.get("payer", {})
    email = (payer.get("email") or "").lower().strip()
    first_name = payer.get("firstName", "")
    last_name = payer.get("lastName", "")
    full_name = f"{first_name} {last_name}".strip()

    if not email:
        logger.warning("HelloAsso webhook: no payer email in payload")
        return JSONResponse({"ok": True, "skipped": True})

    # ── Look up or create user ──────────────────────────────────────────
    user = db.query(models.User).filter(models.User.email == email).first()
    has_account = user is not None

    if user:
        if user.ticket_purchased:
            return JSONResponse({"ok": True, "already_purchased": True})
        user.ticket_purchased = True
        if not user.name or user.name == email:
            user.name = full_name or user.name
    else:
        # Create stub account — user will set password on registration
        user = models.User(
            name=full_name or email,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            ticket_purchased=True,
        )
        db.add(user)

    # Record transaction
    amount_cents = data.get("amount", {}).get("total", 0)
    db.flush()  # Ensure user.id is set for new users
    transaction = models.Transaction(
        user_id=user.id,
        amount_cents=amount_cents,
        type="ticket",
        description="Billet HelloAsso",
    )
    db.add(transaction)
    db.commit()
    db.refresh(user)

    # ── Send welcome email (HelloAsso handles the actual ticket PDF) ───
    try:
        send_welcome_email(user.email, user.name, has_account)
    except Exception as e:
        logger.error(f"HelloAsso webhook: failed to send welcome email: {e}")

    logger.info(f"HelloAsso webhook: ticket activated for {email}")
    return JSONResponse({"ok": True, "user_id": user.id, "ticket_activated": True})
