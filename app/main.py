import os
from sqlalchemy import text, inspect
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import RedirectToLogin, hash_password
from app.routes import auth, tickets, wallet, admin, webhooks

app = FastAPI(title="Repeat the Monkey #3")

# Create all tables
Base.metadata.create_all(bind=engine)

# ── Lightweight migrations (no alembic needed for small projects) ────────────
def _run_migrations():
    """Add missing columns to existing tables."""
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("users")]
        with engine.begin() as conn:
            if "is_bartender" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_bartender BOOLEAN DEFAULT FALSE"))
            if "is_sub_admin" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_sub_admin BOOLEAN DEFAULT FALSE"))
            if "is_scanner" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_scanner BOOLEAN DEFAULT FALSE"))

_run_migrations()

# Auto-seed admin + drinks on first run
def _auto_seed():
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "admin@rtm.fr")
        admin_name = os.getenv("ADMIN_NAME", "Admin")
        existing_admin = db.query(models.User).filter(models.User.email == admin_email).first()
        if not existing_admin:
            admin_user = models.User(
                name=admin_name,
                email=admin_email,
                password_hash=hash_password(os.getenv("ADMIN_PASSWORD", "admin123")),
                is_admin=True,
                ticket_purchased=True,
            )
            db.add(admin_user)
            db.commit()
        elif existing_admin.name != admin_name:
            existing_admin.name = admin_name
            db.commit()
        if db.query(models.DrinkItem).count() == 0:
            for name, price, emoji in [
                ("Bière pression", 300, "🍺"), ("Bière bouteille", 350, "🍻"),
                ("Vin rouge", 300, "🍷"), ("Vin blanc", 300, "🥂"),
                ("Soft / eau", 150, "🥤"), ("Shot", 250, "🥃"),
            ]:
                db.add(models.DrinkItem(name=name, price_cents=price, emoji=emoji))
            db.commit()
    finally:
        db.close()

_auto_seed()

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
