"""Family shield: freeze risky transfers until the trusted contact decides or the cooling period ends."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.antifraud import mock_center
from app.config import settings
from app.family import contacts, telegram_bot
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
    people = contacts.contacts_of(db, client.id)
    active = [c for c in people if c.status == "active"]
    tc = active[0] if active else None
    pending_loans = db.query(Loan).filter_by(client_id=client.id, status="pending_relative").all()
    frozen = sum(t.amount for t in db.query(Transfer).filter(Transfer.from_account_id == acc.id,
                                                              Transfer.status.in_(PAUSED)))
    call = db.query(CallSession).filter_by(client_id=client.id, status="active").first()
    return {
        "id": client.id, "name": client.name, "age": client.age, "phone": client.phone, "balance": client.balance,
        "frozen": frozen, "shield_enabled": client.shield_enabled, "protection_mode": client.protection_mode,
        "language": client.language, "card": acc.card_mask, "account_id": acc.id,
        # first active contact: kept for screens that name "the" trusted person
        "trusted_contact": contacts.serialize(tc, with_code=True) if tc else None,
        "contacts": [contacts.serialize(c, with_code=True) for c in people],
        "pending_loans": [serialize_loan(l) for l in pending_loans],
        "active_call_id": call.id if call else None,
    }


def serialize_loan(l: Loan) -> dict:
    return {"id": l.id, "client_id": l.client_id, "amount": l.amount, "status": l.status, "created_at": l.created_at,
            "decided_by": l.decided_by}


async def push_client(db: Session, client: Client):
    await hub.broadcast("client_state", client_state(db, client))


async def push_transfer(db: Session, t: Transfer, event: str = "transfer"):
    await hub.broadcast(event, serialize_transfer(db, t))
    await hub.broadcast("metrics", metrics(db))


async def take_loan(db: Session, client: Client, amount: float) -> Loan:
    """Instant loan, unless a trusted contact asked to confirm loans: then the money waits for them."""
    confirmers = [c for c in contacts.active_contacts(db, client.id) if c.confirm_loans]
    loan = Loan(client_id=client.id, amount=amount, status="pending_relative" if client.shield_enabled and confirmers
                else "approved")
    if loan.status == "approved":
        client.balance += amount
    db.add(loan)
    db.commit()
    await hub.broadcast("loan", serialize_loan(loan))
    if loan.status == "pending_relative":
        await telegram_bot.notify_loan_request(db, client, loan)
    await push_client(db, client)
    return loan


async def decide_loan(db: Session, loan: Loan, decision: str, by: str) -> Loan:
    if loan.status != "pending_relative":
        raise ValueError(f"Заявка уже обработана: {loan.status}")
    client = db.get(Client, loan.client_id)
    loan.status, loan.decided_by = ("approved" if decision == "approve" else "rejected"), by
    if loan.status == "approved":
        client.balance += loan.amount
    db.commit()
    await hub.broadcast("loan", serialize_loan(loan))
    await telegram_bot.notify_decision(db, client, f"{'✅ Кредит одобрен' if loan.status == 'approved' else '❌ Кредит отклонён'}: "
                                                   f"{telegram_bot.fmt(loan.amount)} · решение: {by_label(db, by)}")
    await push_client(db, client)
    return loan


def by_label(db: Session, by: str) -> str:
    """'relative:12' -> 'Айдар (сын)'."""
    if by and by.startswith("relative:"):
        tc = db.get(TrustedContact, int(by.split(":")[1]))
        if tc:
            return f"{tc.name} ({tc.relation})"
    return {"cooling_expired": "истёк период охлаждения", "analyst_false_positive": "аналитик банка: ложное срабатывание"
            }.get(by, by)


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

    people = contacts.active_contacts(db, client.id) if client.shield_enabled else []
    new_person = not ctx.known_recipient and to_acc.kind == "person"
    family = contacts.transfer_rules(people, amount, new_person)
    t = Transfer(from_account_id=src.id, to_account_id=to_acc.id, amount=amount, risk_score=a["score"],
                 risk_level=a["level"], reasons=a["reasons"] + family, context=a["context"])
    if (to_acc.flags or {}).get("frozen"):
        t.status = "blocked"
    elif client.shield_enabled and (a["level"] == "high" or family):
        # someone from the family decides; with nobody to ask, a risky transfer waits out the cooling period
        t.status = "pending_relative" if people else "cooling"
        t.cooling_until = datetime.now() + timedelta(seconds=settings.cooling_seconds)
    else:
        t.status = "completed"
        client.balance -= amount
    db.add(t)
    db.commit()

    data = serialize_transfer(db, t)
    if t.status == "pending_relative":
        await telegram_bot.notify_transfer_request(db, client, data)
    elif t.status == "completed":
        await telegram_bot.notify_transfer_done(db, client, data)
    await push_transfer(db, t)
    await push_client(db, client)
    return {"action": t.status, "assessment": a, "transfer": data}


async def complete(db: Session, t: Transfer, by: str):
    src = db.get(Account, t.from_account_id)
    client = db.get(Client, src.client_id)
    if client.balance < t.amount:
        t.status, t.decided_by = "rejected", f"{by}: недостаточно средств"
    else:
        client.balance -= t.amount
        t.status, t.decided_by = "completed", by
    db.commit()
    data = serialize_transfer(db, t)
    if t.status == "completed":
        await telegram_bot.notify_decision(db, client, f"✅ Перевод {telegram_bot.fmt(t.amount)} → {data['to']['bank']} "
                                                       f"{data['to']['card']} выполнен · {by_label(db, by)}")
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
    await telegram_bot.notify_decision(db, client, f"❌ Перевод {telegram_bot.fmt(t.amount)} отклонён · {by_label(db, by)}. "
                                                   "Деньги остались на счёте.")
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
    false_pauses = [t for t in paused_ever if t.false_positive or (t.decided_by or "").startswith("relative")
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
