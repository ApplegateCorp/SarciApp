import stripe
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import get_current_user, get_current_user_or_redirect
from app.qr_utils import generate_qr_base64
from app.config import STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_TICKET_PRICE_ID, BASE_URL

router = APIRouter()
templates = Jinja2Templates(directory="templates")
stripe.api_key = STRIPE_SECRET_KEY


@router.get("/ticket", response_class=HTMLResponse)
async def ticket_page(request: Request, user: models.User = Depends(get_current_user_or_redirect)):
    qr_base64 = generate_qr_base64(user.token)
    return templates.TemplateResponse("ticket.html", {
        "request": request,
        "user": user,
        "qr_base64": qr_base64,
        "balance": user.balance_cents / 100,
        "stripe_pk": STRIPE_PUBLISHABLE_KEY,
        "paid": request.query_params.get("session_id") is not None,
    })


@router.post("/ticket/buy/session", response_class=JSONResponse)
async def create_ticket_session(user: models.User = Depends(get_current_user)):
    """Create an embedded Checkout session for ticket purchase."""
    if user.ticket_purchased:
        return JSONResponse({"error": "Already purchased."}, status_code=400)

    session = stripe.checkout.Session.create(
        ui_mode="embedded",
        payment_method_types=["card"],
        line_items=[{"price": STRIPE_TICKET_PRICE_ID, "quantity": 1}],
        mode="payment",
        return_url=f"{BASE_URL}/ticket?session_id={{CHECKOUT_SESSION_ID}}",
        customer_email=user.email,
        metadata={"type": "ticket", "user_id": str(user.id)},
    )
    return JSONResponse({"clientSecret": session.client_secret})
