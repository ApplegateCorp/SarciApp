from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
from app import models
from app.auth import RedirectToLogin
from app.routes import auth, tickets, wallet, admin, webhooks

app = FastAPI(title="Sarcitopia")

# Create all tables
Base.metadata.create_all(bind=engine)

# Redirect to /login when not authenticated on HTML pages
@app.exception_handler(RedirectToLogin)
async def redirect_to_login_handler(request: Request, exc: RedirectToLogin):
    return RedirectResponse("/login", status_code=302)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(wallet.router)
app.include_router(admin.router)
app.include_router(webhooks.router)
