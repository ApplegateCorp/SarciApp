from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.auth import get_current_user_or_redirect
from app.qr_utils import generate_qr_base64
from app.templates_config import create_templates

router = APIRouter()
templates = create_templates()


@router.get("/ticket", response_class=HTMLResponse)
async def ticket_page(request: Request, user=Depends(get_current_user_or_redirect)):
    qr_base64 = generate_qr_base64(user.token)
    return templates.TemplateResponse("ticket.html", {
        "request": request,
        "user": user,
        "qr_base64": qr_base64,
        "balance": user.balance_cents / 100,
    })
