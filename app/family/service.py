"""Family shield: freeze risky transfers until the trusted contact decides or the cooling period ends."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.antifraud import mock_center
from app.config import settings
from app.family import telegram_bot
from app.graph import scoring
from app.models import Account, CallSession, Client, Loan, Transfer, TrustedContact
from app.risk import engine
from app.ws import hub

PAUSED = ("pending_relative", "cooling")


def account_of(db: Session, client: Client) -> Account:
    return db.query(Account).filter_by(client_id=client.id).first()


def serialize_transfer(db: Session, t: Transfer) -> dict:
    src, dst = db.get(Account, t.from_account_id), db.get(Account, t.to_account_id)
    client = db.get(Client, src.client_id) if src.client_id else None
    return {
        "id": t.id, "amount": t.amount, "status": t.status, "risk_score": t.risk_score, "risk_level": t.risk_level,
        "reasons": t.reasons, "context": t.context, "created_at": t.created_at, "cooling_until": t.cooling_until,
        "decided_by": t.decided_by, "false_positive": t.false_positive,
        "from": {"id": src.id, "name": src.owner_name, "bank": src.bank, "card": src.card_mask,
                 "client_id": src.client_id, "age": client.age if client else None},
        "to": {"id": dst.id, "name": dst.owner_name, "bank": dst.bank, "card": dst.card_mask,
               "external": dst.is_external, "risk_score": dst.risk_score},
    }


def client_state(db: Session, client: Client) -> dict:
    acc = account_of(db, client)
    tc = db.query(TrustedContact).filter_by(client_id=client.id).first()
    frozen = sum(t.amount for t in db.query(Transfer).filter(Transfer.from_account_id == acc.id,
                                                              Transfer.status.in_(PAUSED)))
    call = db.query(CallSession).filter_by(client_id=client.id, status="active").first()
    return {
        "id": client.id, "name": client.name, "age": client.age, "phone": client.phone, "balance": client.balance,
        "frozen": frozen, "shield_enabled": client.shield_enabled, "protection_mode": client.protection_mode,
        "language": client.language, "card": acc.card_mask, "account_id": acc.id,
        "trusted_contact": {"id": tc.id, "name": tc.name, "relation": tc.relation, "phone": tc.phone,
                            "link_code": tc.link_code, "threshold": tc.amount_threshold,
                            "telegram_linked": tc.telegram_chat_id is not None} if tc else None,
        "active_call_id": call.id if call else None,
    }


async def push_client(db: Session, client: Client):
    await hub.broadcast("client_state", client_state(db, client))


async def push_transfer(db: Session, t: Transfer, event: str = "transfer"):
    await hub.broadcast(event, serialize_transfer(db, t))
    await hub.broadcast("metrics", metrics(db))


async def take_loan(db: Session, client: Client, amount: float) -> Loan:
    loan = Loan(client_id=client.id, amount=amount)
    client.balance += amount
    db.add(loan)
    db.commit()
    await hub.broadcast("loan", {"client_id": client.id, "amount": amount, "created_at": loan.created_at})
    await push_client(db, client)
    return loan


async def create_transfer(db: Session, client: Client, to_acc: Account, amount: float,
                          behavior: dict | None = None, answers: dict | None = None) -> dict:
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    if amount > client.balance:
        raise ValueError("Недостаточно средств")
    src = account_of(db, client)
    if to_acc.id == src.id:
        raise ValueError("Нельзя перевести на свой же счёт")
    ctx = engine.build_ctx(db, client, src, to_acc, amount, behavior)
    a = engine.evaluate(ctx)
    if client.shield_enabled and a["level"] == "medium":
        if answers is None:
            return {"action": "questions", "assessment": a}
        a = engine.escalate_with_answers(a, answers)
    if not client.shield_enabled and a["level"] != "low":
        a = {**a, "reasons": a["reasons"] + [{"code": "shield_off", "points": 0, "ru": "Семейный щит выключен",
                                              "kk": "Отбасылық қалқан өшірулі"}]}

    t = Transfer(from_account_id=src.id, to_account_id=to_acc.id, amount=amount, risk_score=a["score"],
                 risk_level=a["level"], reasons=a["reasons"], context=a["context"])
    tc = db.query(TrustedContact).filter_by(client_id=client.id).first()
    if (to_acc.flags or {}).get("frozen"):
        t.status = "blocked"
    elif a["level"] == "high" and client.shield_enabled:
        t.status = "pending_relative" if tc and amount >= tc.amount_threshold else "cooling"
        t.cooling_until = datetime.now() + timedelta(seconds=settings.cooling_seconds)
    else:
        t.status = "completed"
        client.balance -= amount
    db.add(t)
    db.commit()

    if t.status == "pending_relative":
        await telegram_bot.send_transfer_request(tc, serialize_transfer(db, t), client)
    await push_transfer(db, t)
    await push_client(db, client)
    return {"action": t.status, "assessment": a, "transfer": serialize_transfer(db, t)}


async def complete(db: Session, t: Transfer, by: str):
    src = db.get(Account, t.from_account_id)
    client = db.get(Client, src.client_id)
    if client.balance < t.amount:
        t.status, t.decided_by = "rejected", f"{by}: недостаточно средств"
    else:
        client.balance -= t.amount
        t.status, t.decided_by = "completed", by
    db.commit()
    await push_transfer(db, t)
    await push_client(db, client)


async def decide(db: Session, t: Transfer, decision: str, by: str = "relative_web") -> dict:
    if t.status not in PAUSED:
        raise ValueError(f"Перевод уже обработан: {t.status}")
    if decision == "approve":
        await complete(db, t, by)
        return {"status": t.status}
    if decision != "reject":
        raise ValueError("decision: approve | reject")
    t.status, t.decided_by = "rejected", by
    dst = db.get(Account, t.to_account_id)
    dst.flags = {**(dst.flags or {}), "confirmed_drop": True,
                 "complaints": int((dst.flags or {}).get("complaints", 0)) + 1}
    db.commit()
    sig = mock_center.send_signal(db, dst, "Доверенное лицо отклонило перевод под давлением мошенников",
                                  {"transfer_id": t.id, "amount": t.amount})
    scoring.compute(db)
    src = db.get(Account, t.from_account_id)
    client = db.get(Client, src.client_id)
    await hub.broadcast("antifraud_signal", mock_center.serialize(db, sig))
    await hub.broadcast("graph_updated", {"focus": dst.id, "reason": "relative_rejected"})
    await push_transfer(db, t)
    await push_client(db, client)
    return {"status": t.status, "signal_id": sig.id}


async def tick(db: Session):
    """Release transfers whose cooling period has passed without a decision."""
    due = db.query(Transfer).filter(Transfer.status.in_(PAUSED), Transfer.cooling_until <= datetime.now()).all()
    for t in due:
        await complete(db, t, "cooling_expired")


async def fast_forward(db: Session) -> int:
    rows = db.query(Transfer).filter(Transfer.status.in_(PAUSED)).all()
    for t in rows:
        t.cooling_until = datetime.now() - timedelta(seconds=1)
    db.commit()
    await tick(db)
    return len(rows)


def metrics(db: Session) -> dict:
    live = db.query(Transfer).filter(Transfer.synthetic.is_(False)).all()
    stopped = [t for t in live if t.status in ("rejected", "blocked") and not t.false_positive]
    paused_ever = [t for t in live if t.risk_level == "high" or t.status in PAUSED]
    false_pauses = [t for t in paused_ever if t.false_positive or t.decided_by in ("relative_web", "relative_telegram")
                    and t.status == "completed"]
    risky_calls = db.query(CallSession).filter(CallSession.status == "active", CallSession.risk_score >= 0.5).count()
    g = scoring.metrics(db)
    return {
        "saved": sum(t.amount for t in stopped),
        "stopped": len(stopped),
        "paused_now": sum(1 for t in live if t.status in PAUSED),
        "risky_calls": risky_calls,
        "droppers_found": g["droppers_found"],
        "precision": g["precision"],
        "recall": g["recall"],
        "false_pause_rate": round(len(false_pauses) / len(paused_ever), 2) if paused_ever else 0,
    }
