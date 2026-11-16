"""Stub of the National Antifraud Centre exchange. Real integration would be an authenticated API."""
import random
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Account, AntifraudSignal, Client, Transfer

CENTER = "Национальный Антифрод-центр (заглушка)"


def _ticket() -> str:
    return f"AFC-{datetime.now():%Y%m%d}-{random.randint(10000, 99999)}"


def send_signal(db: Session, account: Account, reason: str, extra: dict | None = None) -> AntifraudSignal:
    sig = AntifraudSignal(account_id=account.id, direction="out", payload={
        "center": CENTER, "ticket": _ticket(), "bank": account.bank, "card": account.card_mask,
        "owner": account.owner_name, "risk_score": account.risk_score, "reason": reason, **(extra or {}),
    })
    db.add(sig)
    db.commit()
    return sig


def receive_signal(db: Session, account: Account, reason: str = "Карта используется в мошеннических схемах") -> dict:
    account.flags = {**(account.flags or {}), "antifraud": True}
    sig = AntifraudSignal(account_id=account.id, direction="in", payload={
        "center": CENTER, "ticket": _ticket(), "bank": account.bank, "card": account.card_mask, "reason": reason})
    db.add(sig)
    db.commit()
    senders = (db.query(Client).join(Account, Account.client_id == Client.id)
               .join(Transfer, Transfer.from_account_id == Account.id)
               .filter(Transfer.to_account_id == account.id).distinct().all())
    return {"signal": serialize(db, sig), "warned_clients": [{"id": c.id, "name": c.name} for c in senders]}


def serialize(db: Session, s: AntifraudSignal) -> dict:
    return {"id": s.id, "account_id": s.account_id, "direction": s.direction, "payload": s.payload,
            "created_at": s.created_at}


def journal(db: Session, limit: int = 50) -> list[dict]:
    rows = db.query(AntifraudSignal).order_by(AntifraudSignal.id.desc()).limit(limit).all()
    return [serialize(db, s) for s in rows]
