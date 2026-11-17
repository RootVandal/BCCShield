from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now() -> datetime:
    return datetime.now()


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    phone: Mapped[str] = mapped_column(String(32))
    balance: Mapped[float] = mapped_column(Float, default=0)
    shield_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    protection_mode: Mapped[str] = mapped_column(String(8), default="off")  # off / on
    language: Mapped[str] = mapped_column(String(4), default="ru")


class TrustedContact(Base):
    """A person who confirms the client's risky operations. A client can have several.

    status: approval (an existing trusted contact must allow adding them) -> invited (waits for the person to
    accept in Telegram) -> active. declined / removed are kept for the history.
    """
    __tablename__ = "trusted_contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    name: Mapped[str] = mapped_column(String(120))
    relation: Mapped[str] = mapped_column(String(40))
    phone: Mapped[str] = mapped_column(String(32), default="")
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    link_code: Mapped[str] = mapped_column(String(24), default="")
    amount_threshold: Mapped[float] = mapped_column(Float, default=100_000)   # confirm transfers from this amount
    status: Mapped[str] = mapped_column(String(16), default="active")
    confirm_new: Mapped[bool] = mapped_column(Boolean, default=True)          # confirm transfers to new people
    confirm_loans: Mapped[bool] = mapped_column(Boolean, default=True)        # confirm loans
    notify_all: Mapped[bool] = mapped_column(Boolean, default=True)           # see every transfer
    verify_phone: Mapped[bool] = mapped_column(Boolean, default=True)         # Telegram number must match `phone`
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=now, nullable=True)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(120))
    bank: Mapped[str] = mapped_column(String(32))
    card_mask: Mapped[str] = mapped_column(String(32))
    card_key: Mapped[str] = mapped_column(String(48), index=True)  # bank:last4 or phone:+7...
    kind: Mapped[str] = mapped_column(String(16), default="person")  # person/merchant/employer/cash
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)


class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    from_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    to_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_level: Mapped[str] = mapped_column(String(8), default="low")
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    cooling_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    false_positive: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Loan(Base):
    __tablename__ = "loans"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(16), default="approved")      # pending_relative / approved / rejected
    decided_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class CallSession(Base):
    __tablename__ = "call_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_history: Mapped[list] = mapped_column(JSON, default=list)
    matched_phrases: Mapped[list] = mapped_column(JSON, default=list)
    llm_verdict: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/ended


class AntifraudSignal(Base):
    __tablename__ = "antifraud_signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    direction: Mapped[str] = mapped_column(String(4))  # out / in
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
