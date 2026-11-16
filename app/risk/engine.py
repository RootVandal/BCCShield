from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Account, AntifraudSignal, CallSession, Client, Loan, Transfer
from app.risk.rules import RULES, Ctx

LOW_MAX, MEDIUM_MAX = 40, 70


def level_of(score: float) -> str:
    return "low" if score < LOW_MAX else "medium" if score <= MEDIUM_MAX else "high"


def build_ctx(db: Session, client: Client, from_acc: Account, to_acc: Account, amount: float,
              behavior: dict | None = None, now: datetime | None = None) -> Ctx:
    now = now or datetime.now()
    behavior = behavior or {}
    call = (db.query(CallSession).filter_by(client_id=client.id, status="active")
            .order_by(CallSession.started_at.desc()).first())
    loan = db.query(Loan).filter_by(client_id=client.id).order_by(Loan.created_at.desc()).first()
    hist = db.query(Transfer).filter(Transfer.from_account_id == from_acc.id, Transfer.status == "completed").all()
    known = any(t.to_account_id == to_acc.id for t in hist) or db.query(Transfer).filter(
        Transfer.from_account_id == to_acc.id, Transfer.to_account_id == from_acc.id).first() is not None
    has_signal = db.query(AntifraudSignal).filter_by(account_id=to_acc.id, direction="in").first() is not None
    return Ctx(client=client, amount=amount, recipient=to_acc, now=now, call=call, loan=loan,
               history=[t.amount for t in hist], known_recipient=known, has_signal=has_signal,
               pasted=bool(behavior.get("pasted")), fill_seconds=behavior.get("fill_seconds"))


def evaluate(ctx: Ctx) -> dict:
    reasons = []
    for code, rule in RULES.items():
        res = rule(ctx)
        if res:
            pts, ru, kk = res
            reasons.append({"code": code, "points": pts, "ru": ru, "kk": kk})
    score = min(100, sum(r["points"] for r in reasons))
    if ctx.client.protection_mode == "on":
        reasons.insert(0, {"code": "protection_mode", "points": 0,
                           "ru": "Включён режим защиты после подозрительного звонка",
                           "kk": "Күдікті қоңыраудан кейін қорғау режимі қосулы"})
        score = max(score, 75)
    reasons.sort(key=lambda r: -r["points"])
    context = {
        "call_active": ctx.call is not None,
        "call_risk": round(ctx.call.risk_score, 2) if ctx.call else None,
        "loan_minutes_ago": round((ctx.now - ctx.loan.created_at).total_seconds() / 60, 1) if ctx.loan else None,
        "new_recipient": not ctx.known_recipient,
        "protection_mode": ctx.client.protection_mode,
        "pasted": ctx.pasted,
        "fill_seconds": ctx.fill_seconds,
    }
    return {"score": score, "level": level_of(score), "reasons": reasons, "context": context}


def escalate_with_answers(assessment: dict, answers: dict) -> dict:
    """Medium-risk questionnaire: any 'yes' raises the level to high."""
    labels = {
        "on_call": ("Клиент подтвердил: сейчас идёт звонок", "Клиент растады: қазір қоңырау жүріп жатыр"),
        "safe_account": ("Клиента просят перевести на «безопасный счёт»", "Клиенттен «қауіпсіз шотқа» аударуды сұрайды"),
        "impersonation": ("Звонящий представился банком/полицией", "Қоңырау шалушы банк/полиция атынан"),
    }
    yes = [k for k, v in (answers or {}).items() if v and k in labels]
    if not yes:
        return assessment
    reasons = [{"code": f"answer_{k}", "points": 15, "ru": labels[k][0], "kk": labels[k][1]} for k in yes]
    score = max(75, min(100, assessment["score"] + 15 * len(yes)))
    return {**assessment, "score": score, "level": "high", "reasons": reasons + assessment["reasons"]}


def find_or_create_recipient(db: Session, bank: str, card: str | None, phone: str | None) -> Account:
    bank = (bank or "BCC").strip()
    if phone:
        digits = "".join(ch for ch in phone if ch.isdigit())
        phone_norm = "+7" + digits[-10:]
        client = db.query(Client).filter(Client.phone == phone_norm).first()
        if client and bank.upper() == "BCC":
            acc = db.query(Account).filter_by(client_id=client.id).first()
            if acc:
                return acc
        key = f"phone:{phone_norm}"
        acc = db.query(Account).filter_by(card_key=key).first()
        if acc:
            return acc
        acc = Account(owner_name=f"Получатель {phone_norm[:5]}•••{phone_norm[-2:]}", bank=bank,
                      card_mask=f"тел. ••{phone_norm[-4:]}", card_key=key, is_external=bank.upper() != "BCC")
    else:
        digits = "".join(ch for ch in (card or "") if ch.isdigit())
        if len(digits) < 4:
            raise ValueError("Укажите номер карты или телефон")
        last4 = digits[-4:]
        key = f"{bank.lower()}:{last4}"
        acc = db.query(Account).filter(or_(Account.card_key == key)).first()
        if acc:
            return acc
        acc = Account(owner_name="Новый получатель", bank=bank, card_mask=f"•• {last4}", card_key=key,
                      is_external=bank.upper() != "BCC")
    db.add(acc)
    db.flush()
    return acc
