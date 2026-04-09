import stripe
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import get_current_user, get_current_user_or_redirect
from app.config import STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, BASE_URL
from app.templates_config import create_templates

router = APIRouter()
templates = create_templates()
stripe.api_key = STRIPE_SECRET_KEY

TOPUP_AMOUNTS = [5, 10, 20, 50]


@router.get("/wallet", response_class=HTMLResponse)
async def wallet_page(
    request: Request,
    user: models.User = Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user.id)
        .order_by(models.Transaction.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse("wallet.html", {
        "request": request,
        "user": user,
        "balance": user.balance_cents / 100,
        "transactions": transactions,
        "topup_amounts": TOPUP_AMOUNTS,
        "stripe_pk": STRIPE_PUBLISHABLE_KEY,
    })


@router.post("/wallet/topup/intent", response_class=JSONResponse)
async def create_topup_intent(
    request: Request,
    user: models.User = Depends(get_current_user),
):
    """Create a PaymentIntent for wallet top-up (Apple Pay / Google Pay)."""
    body = await request.json()
    amount = body.get("amount")

    if not amount or amount not in TOPUP_AMOUNTS:
        return JSONResponse({"error": "Montant invalide."}, status_code=400)

    intent = stripe.PaymentIntent.create(
        amount=amount * 100,
        currency="eur",
        metadata={
            "type": "topup",
            "user_id": str(user.id),
            "amount_cents": str(amount * 100),
        },
        automatic_payment_methods={"enabled": True},
    )

    return JSONResponse({"clientSecret": intent.client_secret})


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    user: models.User = Depends(get_current_user_or_redirect),
    db: Session = Depends(get_db),
):
    """Full order history for a user — grouped by drink orders."""
    drink_txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user.id, models.Transaction.type == "drink")
        .order_by(models.Transaction.created_at.desc())
        .all()
    )
    all_txs = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user.id)
        .order_by(models.Transaction.created_at.desc())
        .all()
    )
    total_spent_bar = sum(abs(tx.amount_cents) for tx in drink_txs)
    total_orders = len(drink_txs)
    total_recharged = sum(tx.amount_cents for tx in all_txs if tx.type == "topup")

    return templates.TemplateResponse("history.html", {
        "request": request,
        "user": user,
        "drink_orders": drink_txs,
        "all_transactions": all_txs,
        "total_spent_bar": total_spent_bar / 100,
        "total_orders": total_orders,
        "total_recharged": total_recharged / 100,
        "balance": user.balance_cents / 100,
    })
