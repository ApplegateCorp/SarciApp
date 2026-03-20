import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from app.qr_utils import generate_qr_base64
from app.email_utils import send_ticket_email

router = APIRouter()
stripe.api_key = STRIPE_SECRET_KEY


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        payment_type = metadata.get("type")
        user_id = metadata.get("user_id")

        if not user_id:
            return JSONResponse({"ok": True})

        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        if not user:
            return JSONResponse({"ok": True})

        if payment_type == "ticket":
            if not user.ticket_purchased:
                user.ticket_purchased = True
                transaction = models.Transaction(
                    user_id=user.id,
                    amount_cents=session["amount_total"],
                    type="ticket",
                    description="Festival ticket",
                    stripe_session_id=session["id"],
                )
                db.add(transaction)
                db.commit()
                db.refresh(user)

                # Send ticket email with QR code
                try:
                    qr_base64 = generate_qr_base64(user.token)
                    send_ticket_email(user.email, user.name, user.token, qr_base64)
                except Exception:
                    pass  # Don't fail the webhook if email fails

        elif payment_type == "topup":
            amount_cents = int(metadata.get("amount_cents", 0))
            if amount_cents > 0:
                user.balance_cents += amount_cents
                transaction = models.Transaction(
                    user_id=user.id,
                    amount_cents=amount_cents,
                    type="topup",
                    description=f"Top-up {amount_cents // 100}€",
                    stripe_session_id=session["id"],
                )
                db.add(transaction)
                db.commit()

    return JSONResponse({"ok": True})
