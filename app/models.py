import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    token = Column(String, unique=True, default=generate_uuid, nullable=False)  # Used in QR code

    # Ticket
    ticket_purchased = Column(Boolean, default=False)
    ticket_scanned = Column(Boolean, default=False)  # Entry validation (one-time)

    # Wallet (stored in cents to avoid float issues, e.g. 500 = 5.00 €)
    balance_cents = Column(Integer, default=0)

    is_admin = Column(Boolean, default=False)
    is_sub_admin = Column(Boolean, default=False)
    is_bartender = Column(Boolean, default=False)
    is_scanner = Column(Boolean, default=False)   # Can scan tickets at entry
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="user")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount_cents = Column(Integer, nullable=False)  # Positive = credit, Negative = debit
    type = Column(String, nullable=False)           # "topup", "drink", "ticket"
    description = Column(String, default="")
    stripe_session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class PendingTicket(Base):
    __tablename__ = "pending_tickets"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticket_type = Column(String, nullable=False)       # e.g. "Monkey Pass - 2 Jours"
    amount_cents = Column(Integer, default=0)
    assigned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    buyer = relationship("User", foreign_keys=[buyer_id], backref="pending_tickets_bought")
    recipient = relationship("User", foreign_keys=[recipient_id])


class DrinkItem(Base):
    __tablename__ = "drink_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price_cents = Column(Integer, nullable=False)
    available = Column(Boolean, default=True)
    emoji = Column(String, default="🍺")
