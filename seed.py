"""
Run once after first launch to create the admin user and default drinks:
  python seed.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app.database import Base, engine, SessionLocal
from app import models
from app.auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── Admin user ───────────────────────────────────────────────────────────────
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@festival.fr")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

if not db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first():
    admin = models.User(
        name=ADMIN_NAME,
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        is_admin=True,
        ticket_purchased=True,
    )
    db.add(admin)
    print(f"Created admin: {ADMIN_EMAIL}")
else:
    print(f"Admin already exists: {ADMIN_EMAIL}")

# ── Default drinks ───────────────────────────────────────────────────────────
DEFAULT_DRINKS = [
    ("Bière pression", 300, "🍺"),
    ("Bière bouteille", 350, "🍻"),
    ("Vin rouge", 300, "🍷"),
    ("Vin blanc", 300, "🥂"),
    ("Soft / eau", 150, "🥤"),
    ("Shot", 250, "🥃"),
]

if db.query(models.DrinkItem).count() == 0:
    for name, price_cents, emoji in DEFAULT_DRINKS:
        db.add(models.DrinkItem(name=name, price_cents=price_cents, emoji=emoji))
    print(f"Created {len(DEFAULT_DRINKS)} default drinks.")
else:
    print("Drinks already seeded.")

db.commit()
db.close()
print("Done.")
