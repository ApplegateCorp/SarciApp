from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth import get_current_user_optional
from app.qr_utils import generate_qr_base64

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/ticket", response_class=HTMLResponse)
async def ticket_page(request: Request, user=Depends(get_current_user_optional)):
    qr_base64 = None
    balance = 0
    if user:
        qr_base64 = generate_qr_base64(user.token)
        balance = user.balance_cents / 100
    return templates.TemplateResponse("ticket.html", {
        "request": request,
        "user": user,
        "qr_base64": qr_base64,
        "balance": balance,
    })
