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
OPS = {"transfer": "Перевод", "cash": "Снятие наличных", "deposit": "Закрытие депозита"}
# bank-side pseudo-accounts that cash withdrawals and deposit closures "go to" (kept out of the drop graph)
OP_ACCOUNTS = {
    "cash": {"card_key": "bcc:cash-desk", "owner_name": "Снятие наличных", "card_mask": "касса / банкомат"},
    "deposit": {"card_key": "bcc:deposit", "owner_name": "Закрытие депозита", "card_mask": "депозит → карта"},
}


def op_account(db: Session, kind: str) -> Account:
    spec = OP_ACCOUNTS[kind]
    acc = db.query(Account).filter_by(card_key=spec["card_key"]).first()
    if not acc:
        acc = Account(bank="BCC", kind="cash", is_external=True, **spec)
        db.add(acc)
        db.flush()
    return acc


def account_of(db: Session, client: Client) -> Account:
    return db.query(Account).filter_by(client_id=client.id).first()


def serialize_transfer(db: Session, t: Transfer) -> dict:
    src, dst = db.get(Account, t.from_account_id), db.get(Account, t.to_account_id)
    client = db.get(Client, src.client_id) if src.client_id else None
    kind = t.kind or "transfer"
    return {
        "id": t.id, "kind": kind, "title": OPS.get(kind, "Перевод"), "amount": t.amount, "status": t.status, "risk_score": t.risk_score, "risk_level": t.risk_level,
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
    pending_loans = db.query(Loan).filter(Loan.client_id == client.id, Loan.status.in_(PAUSED)).all()
    frozen = sum(t.amount for t in db.query(Transfer).filter(Transfer.from_account_id == acc.id,
                                                              Transfer.status.in_(PAUSED), Transfer.kind != "deposit"))
    call = db.query(CallSession).filter_by(client_id=client.id, status="active").first()
    return {
        "id": client.id, "name": client.name, "age": client.age, "phone": client.phone, "balance": client.balance,
        "deposit": client.deposit or 0, "telecom_alert": engine.telecom_active(client),
        "frozen": frozen, "shield_enabled": client.shield_enabled, "protection_mode": client.protection_mode,
        "language": client.language, "card": acc.card_mask, "account_id": acc.id,
        # first active contact: kept for screens that name "the" trusted person
        "trusted_contact": contacts.serialize(tc, with_code=True) if tc else None,
        "contacts": [contacts.serialize(c, with_code=True) for c in people],
        "pending_loans": [serialize_loan(l) for l in pending_loans],
        "active_call_id": call.id if call else None,
        "remote_app": client.remote_app,
    }


def serialize_loan(l: Loan) -> dict:
    return {"id": l.id, "client_id": l.client_id, "amount": l.amount, "status": l.status, "created_at": l.created_at,
            "decided_by": l.decided_by, "cooling_until": l.cooling_until, "reasons": l.reasons or []}


def danger_reasons(db: Session, client: Client) -> list[dict]:
    """Why the bank must not hand out money right now: a risky call, an operator signal, protection mode."""
    out = []
    call = (db.query(CallSession).filter_by(client_id=client.id, status="active")
            .order_by(CallSession.started_at.desc()).first())
    if call and call.risk_score >= 0.5:
        from app.risk.rules import call_line
        ru, kk = call_line(call, client)
        out.append({"code": "call_risk", "ru": ru, "kk": kk})
    if client.remote_app and not (out and call.source == "phone"):  # a phone call's line already names it
        out.append({"code": "remote_app", "ru": f"На телефоне открыт удалённый доступ ({client.remote_app})",
                    "kk": f"Телефонда қашықтан қол жеткізу ашық ({client.remote_app})"})
    if engine.telecom_active(client):
        out.append({"code": "telecom_signal", "ru": "Оператор связи сообщил о подозрительном звонке («Телеком Антифрод»)",
                    "kk": "Байланыс операторы күдікті қоңырау туралы хабарлады («Телеком Антифрод»)"})
    if client.protection_mode == "on":
        out.append({"code": "protection_mode", "ru": "Включён режим защиты после подозрительного звонка",
                    "kk": "Күдікті қоңыраудан кейін қорғау режимі қосулы"})
    return out


async def push_client(db: Session, client: Client):
    await hub.broadcast("client_state", client_state(db, client))


async def push_transfer(db: Session, t: Transfer, event: str = "transfer"):
    await hub.broadcast(event, serialize_transfer(db, t))
    await hub.broadcast("metrics", metrics(db))


async def take_loan(db: Session, client: Client, amount: float) -> Loan:
    """Instant loan, except when the bank already knows the client is being worked on (risky call, operator
    signal, protection mode) or the family asked to confirm loans: then a trusted contact decides; with nobody
    to ask, the money waits out the cooling period."""
    people = contacts.active_contacts(db, client.id) if client.shield_enabled else []
    danger = danger_reasons(db, client) if client.shield_enabled else []
    family = [] if danger else [c for c in people if c.confirm_loans]
    reasons = danger + ([{"code": "family_loans", "ru": "По правилу семьи кредиты подтверждает доверенное лицо",
                          "kk": "Отбасы ережесі бойынша несиені сенімді адам растайды"}] if family else [])
    status = "pending_relative" if people and (danger or family) else "cooling" if danger else "approved"
    loan = Loan(client_id=client.id, amount=amount, status=status, reasons=reasons,
                cooling_until=datetime.now() + timedelta(seconds=settings.cooling_seconds) if status == "cooling" else None)
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
    if loan.status not in PAUSED:
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


async def create_operation(db: Session, client: Client, kind: str, amount: float | None = None,
                           behavior: dict | None = None, answers: dict | None = None) -> dict:
    """Cash withdrawal or early deposit closure: same risk engine, same family confirmation as transfers."""
    if kind not in OP_ACCOUNTS:
        raise ValueError("kind: cash | deposit")
    if kind == "deposit":
        amount = client.deposit or 0
        if amount <= 0:
            raise ValueError("Депозит уже закрыт")
    return await create_transfer(db, client, op_account(db, kind), amount or 0, behavior, answers, kind=kind)


async def create_transfer(db: Session, client: Client, to_acc: Account, amount: float,
                          behavior: dict | None = None, answers: dict | None = None, kind: str = "transfer") -> dict:
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    if kind == "deposit":
        if amount > (client.deposit or 0):
            raise ValueError("Сумма больше депозита")
        if db.query(Transfer).filter(Transfer.kind == "deposit", Transfer.status.in_(PAUSED),
                                     Transfer.from_account_id == account_of(db, client).id).first():
            raise ValueError("Закрытие депозита уже ждёт решения")
    elif amount > client.balance:
        raise ValueError("Недостаточно средств")
    src = account_of(db, client)
    if to_acc.id == src.id:
        raise ValueError("Нельзя перевести на свой же счёт")
    ctx = engine.build_ctx(db, client, src, to_acc, amount, behavior, kind=kind)
    a = engine.evaluate(ctx)
    if client.shield_enabled and a["level"] == "medium":
        if answers is None:
            return {"action": "questions", "assessment": a}
        a = engine.escalate_with_answers(a, answers)
    if not client.shield_enabled and a["level"] != "low":
        a = {**a, "reasons": a["reasons"] + [{"code": "shield_off", "points": 0, "ru": "Семейный щит выключен",
                                              "kk": "Отбасылық қалқан өшірулі"}]}

    people = contacts.active_contacts(db, client.id) if client.shield_enabled else []
    new_person = kind == "transfer" and not ctx.known_recipient and to_acc.kind == "person"
    # closing a deposit keeps the money with the client: the family is asked only when the risk is high
    family = [] if kind == "deposit" else contacts.transfer_rules(people, amount, new_person)
    t = Transfer(from_account_id=src.id, to_account_id=to_acc.id, amount=amount, risk_score=a["score"],
                 risk_level=a["level"], reasons=a["reasons"] + family, context=a["context"], kind=kind)
    if (to_acc.flags or {}).get("frozen"):
        t.status = "blocked"
    elif client.shield_enabled and (a["level"] == "high" or family):
        # someone from the family decides; with nobody to ask, a risky transfer waits out the cooling period
        t.status = "pending_relative" if people else "cooling"
        t.cooling_until = datetime.now() + timedelta(seconds=settings.cooling_seconds)
    else:
        t.status = "completed"
        apply_money(client, t)
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


def apply_money(client: Client, t: Transfer):
    if t.kind == "deposit":
        client.deposit = (client.deposit or 0) - t.amount
        client.balance += t.amount
    else:
        client.balance -= t.amount


def op_line(data: dict) -> str:
    """'Перевод 40 000 ₸ → BCC •• 7720' / 'Снятие наличных 2 000 000 ₸'."""
    s = f"{data['title']} {telegram_bot.fmt(data['amount'])}"
    return s + (f" → {data['to']['bank']} {data['to']['card']}" if data["kind"] == "transfer" else "")


async def complete(db: Session, t: Transfer, by: str):
    src = db.get(Account, t.from_account_id)
    client = db.get(Client, src.client_id)
    short = (client.deposit or 0) < t.amount if t.kind == "deposit" else client.balance < t.amount
    if short:
        t.status, t.decided_by = "rejected", f"{by}: недостаточно средств"
    else:
        apply_money(client, t)
        t.status, t.decided_by = "completed", by
    db.commit()
    data = serialize_transfer(db, t)
    if t.status == "completed":
        await telegram_bot.notify_decision(db, client, f"✅ {op_line(data)}: выполнено · {by_label(db, by)}")
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
    src = db.get(Account, t.from_account_id)
    client = db.get(Client, src.client_id)
    if t.kind != "transfer":  # cash desk / deposit: nobody to report, the money simply stays
        db.commit()
        await telegram_bot.notify_decision(db, client, f"❌ {op_line(serialize_transfer(db, t))}: отклонено · "
                                                       f"{by_label(db, by)}. Деньги остались у клиента.")
        await push_transfer(db, t)
        await push_client(db, client)
        return {"status": t.status}
    dst = db.get(Account, t.to_account_id)
    dst.flags = {**(dst.flags or {}), "confirmed_drop": True,
                 "complaints": int((dst.flags or {}).get("complaints", 0)) + 1}
    db.commit()
    sig = mock_center.send_signal(db, dst, "Доверенное лицо отклонило перевод под давлением мошенников",
                                  {"transfer_id": t.id, "amount": t.amount})
    scoring.compute(db)
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
    for loan in db.query(Loan).filter(Loan.status == "cooling", Loan.cooling_until <= datetime.now()).all():
        await decide_loan(db, loan, "approve", "cooling_expired")


async def fast_forward(db: Session) -> int:
    rows = db.query(Transfer).filter(Transfer.status.in_(PAUSED)).all()
    loans = db.query(Loan).filter(Loan.status == "cooling").all()
    for t in [*rows, *loans]:
        t.cooling_until = datetime.now() - timedelta(seconds=1)
    db.commit()
    await tick(db)
    return len(rows) + len(loans)


def metrics(db: Session) -> dict:
    live = db.query(Transfer).filter(Transfer.synthetic.is_(False)).all()
    stopped = [t for t in live if t.status in ("rejected", "blocked") and not t.false_positive and t.kind != "deposit"]
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


async def telecom_signal(db: Session, client: Client, minutes: int = 15) -> dict:
    """«Телеком Антифрод» pilot (stub): the operator tells the bank a suspicious call is in progress. In production
    this replaces listening to the call: no microphone, works on iOS and Android."""
    client.telecom_alert_until = datetime.now() + timedelta(minutes=minutes)
    if client.shield_enabled:
        client.protection_mode = "on"
    db.commit()
    warning = {"client_id": client.id,
               "ru": "Оператор связи сообщил банку: вам сейчас звонят с номера, замеченного в мошенничестве. "
                     "Не переводите и не снимайте деньги по просьбе звонящего.",
               "kk": "Байланыс операторы банкке хабарлады: сізге алаяқтықта байқалған нөмірден қоңырау шалуда. "
                     "Қоңырау шалушының өтінішімен ақша аудармаңыз және шешпеңіз."}
    await hub.broadcast("client_warning", warning)
    await telegram_bot.notify_call_alert(db, client, "сигнал оператора связи («Телеком Антифрод»)")
    await push_client(db, client)
    return {"telecom_alert_until": client.telecom_alert_until, "protection_mode": client.protection_mode}
