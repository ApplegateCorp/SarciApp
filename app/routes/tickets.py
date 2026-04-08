import secrets
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import get_current_user_or_redirect, hash_password
from app.qr_utils import generate_qr_base64
from app.email_utils import send_welcome_email
from app.templates_config import create_templates

router = APIRouter()
templates = create_templates()


@router.get("/ticket", response_class=HTMLResponse)
async def ticket_page(
    request: Request,
    user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    qr_base64 = generate_qr_base64(user.token)
    pending = (
        db.query(models.PendingTicket)
        .filter(models.PendingTicket.buyer_id == user.id, models.PendingTicket.assigned == False)
        .all()
    )
    return templates.TemplateResponse("ticket.html", {
        "request": request,
        "user": user,
        "qr_base64": qr_base64,
        "balance": user.balance_cents / 100,
        "pending_tickets": pending,
    })


@router.post("/assign-ticket", response_class=HTMLResponse)
async def assign_ticket(
    request: Request,
    ticket_id: int = Form(...),
    email: str = Form(...),
    name: str = Form(...),
    user=Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    """Assign a pending ticket to another person by email."""
    email = email.lower().strip()

    # Verify this pending ticket belongs to the current user
    pending = (
        db.query(models.PendingTicket)
        .filter(
            models.PendingTicket.id == ticket_id,
            models.PendingTicket.buyer_id == user.id,
            models.PendingTicket.assigned == False,
        )
        .first()
    )
    if not pending:
        return RedirectResponse("/ticket", status_code=302)

    # Find or create the recipient account
    recipient = db.query(models.User).filter(models.User.email == email).first()
    if recipient:
        if recipient.ticket_purchased:
            # Already has a ticket — show error
            pending_all = (
                db.query(models.PendingTicket)
                .filter(models.PendingTicket.buyer_id == user.id, models.PendingTicket.assigned == False)
                .all()
            )
            qr_base64 = generate_qr_base64(user.token)
            return templates.TemplateResponse("ticket.html", {
                "request": request,
                "user": user,
                "qr_base64": qr_base64,
                "balance": user.balance_cents / 100,
                "pending_tickets": pending_all,
                "assign_error": f"{email} a déjà un billet.",
            })
        recipient.ticket_purchased = True
        if not recipient.name or recipient.name == email:
            recipient.name = name.strip()
    else:
        recipient = models.User(
            name=name.strip(),
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            ticket_purchased=True,
        )
        db.add(recipient)

    db.flush()

    # Record transaction on the recipient
    tx = models.Transaction(
        user_id=recipient.id,
        amount_cents=pending.amount_cents,
        type="ticket",
        description=pending.ticket_type,
    )
    db.add(tx)

    # Mark pending ticket as assigned
    pending.assigned = True
    pending.recipient_id = recipient.id
    db.commit()

    # Send welcome email to the recipient
    try:
        send_welcome_email(recipient.email, recipient.name, False)
    except Exception:
        pass

    return RedirectResponse("/ticket", status_code=302)
