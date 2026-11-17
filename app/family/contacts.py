"""Trusted contacts of a client: adding, approving, inviting, rules.

Security model (the scammer may control the client's phone):
- The first trusted contact of a client can be added right away: it only adds protection.
- Every next contact must be allowed by an already active one. Otherwise a scammer could make the victim add
  "a bank employee" as a trusted contact and approve the transfers himself.
- Nobody can be added while a suspicious call is going on (protection mode).
- From the client's phone rules can only be made stricter; loosening them, removing an active contact or switching
  the shield off needs a trusted contact.
- An invitation is accepted in Telegram, where the person shares their own phone number; it must match the number
  the client entered (see app/family/telegram_bot.py).
"""
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Client, TrustedContact
from app.security import new_link_code, relative_key

MAX_CONTACTS = 5
LIVE = ("approval", "invited", "active")
RELATIONS = ("сын", "дочь", "внук", "внучка", "брат", "сестра", "муж", "жена", "друг", "соседка", "сосед", "другое")


TRANSLIT = dict(zip("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЫЭЮЯӘҒҚҢӨҰҮҺІ",
                    ["A", "B", "V", "G", "D", "E", "E", "ZH", "Z", "I", "I", "K", "L", "M", "N", "O", "P", "R", "S",
                     "T", "U", "F", "H", "C", "CH", "SH", "SH", "Y", "E", "YU", "YA", "A", "G", "K", "N", "O", "U",
                     "U", "H", "I"]))


def digits(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")[-10:]


def contacts_of(db: Session, client_id: int, statuses=LIVE) -> list[TrustedContact]:
    q = db.query(TrustedContact).filter(TrustedContact.client_id == client_id, TrustedContact.status.in_(statuses))
    return q.order_by(TrustedContact.id).all()


def active_contacts(db: Session, client_id: int) -> list[TrustedContact]:
    return contacts_of(db, client_id, ("active",))


def rules(tc: TrustedContact) -> dict:
    return {"threshold": tc.amount_threshold, "confirm_new": tc.confirm_new, "confirm_loans": tc.confirm_loans,
            "notify_all": tc.notify_all}


def serialize(tc: TrustedContact, with_code: bool = False) -> dict:
    d = {"id": tc.id, "client_id": tc.client_id, "name": tc.name, "relation": tc.relation, "phone": tc.phone,
         "status": tc.status, "telegram_linked": tc.telegram_chat_id is not None, "rules": rules(tc),
         "threshold": tc.amount_threshold, "created_at": tc.created_at}
    if with_code and tc.status == "invited":  # the code is shown to the client only while the invitation is open
        d["link_code"] = tc.link_code
    elif with_code and tc.status == "active" and tc.telegram_chat_id is None:
        d["link_code"] = tc.link_code  # active (seeded / accepted on the web) but Telegram not linked yet
    return d


def _prefix(client: Client) -> str:
    first = (client.name or "BCC").split()[0]
    p = re.sub(r"[^A-Z]", "", "".join(TRANSLIT.get(ch, ch) for ch in first.upper()))[:6]
    return p or "BCC"


def add_contact(db: Session, client: Client, name: str, relation: str, phone: str, rule: dict) -> TrustedContact:
    if client.protection_mode == "on":
        raise ValueError("Во время подозрительного звонка добавлять доверенных лиц нельзя. Положите трубку и "
                         "попробуйте позже.")
    if len(contacts_of(db, client.id)) >= MAX_CONTACTS:
        raise ValueError(f"Можно добавить не больше {MAX_CONTACTS} доверенных лиц")
    if len(digits(phone)) < 10:
        raise ValueError("Укажите номер телефона доверенного лица: по нему он подтвердит приглашение в Telegram")
    if any(digits(c.phone) == digits(phone) for c in contacts_of(db, client.id)):
        raise ValueError("Этот человек уже есть в списке")
    if digits(phone) == digits(client.phone):
        raise ValueError("Нельзя добавить свой собственный номер")
    has_active = bool(active_contacts(db, client.id))
    tc = TrustedContact(client_id=client.id, name=name.strip(), relation=relation.strip() or "другое",
                        phone=phone.strip(), link_code=new_link_code(_prefix(client)),
                        amount_threshold=float(rule.get("threshold", 100_000)),
                        confirm_new=bool(rule.get("confirm_new", True)), confirm_loans=bool(rule.get("confirm_loans", True)),
                        notify_all=bool(rule.get("notify_all", True)), verify_phone=True,
                        status="approval" if has_active else "invited", created_at=datetime.now())
    db.add(tc)
    db.commit()
    return tc


def decide_addition(db: Session, tc: TrustedContact, decision: str) -> TrustedContact:
    """An active trusted contact allows (or not) adding a new one."""
    if tc.status != "approval":
        raise ValueError("Этот запрос уже обработан")
    tc.status = "invited" if decision == "approve" else "declined"
    db.commit()
    return tc


def accept(db: Session, tc: TrustedContact, chat_id: int | None) -> TrustedContact:
    if tc.status != "invited" and not (tc.status == "active" and tc.telegram_chat_id is None):
        raise ValueError("Приглашение уже недействительно")
    if chat_id is not None:
        taken = db.query(TrustedContact).filter(TrustedContact.client_id == tc.client_id, TrustedContact.id != tc.id,
                                                TrustedContact.telegram_chat_id == chat_id,
                                                TrustedContact.status.in_(LIVE)).first()
        if taken:
            raise ValueError("Этот Telegram уже подключён как другое доверенное лицо этого клиента")
        tc.telegram_chat_id = chat_id
    tc.status = "active"
    db.commit()
    return tc


def remove(db: Session, tc: TrustedContact) -> TrustedContact:
    tc.status = "removed" if tc.status == "active" else "declined"
    tc.telegram_chat_id = None if tc.status == "declined" else tc.telegram_chat_id
    db.commit()
    return tc


def update_rules(db: Session, tc: TrustedContact, new: dict, by_relative: bool) -> TrustedContact:
    """The client can only tighten the rules; loosening them needs a trusted contact."""
    cur = rules(tc)
    if not by_relative:
        looser = (("threshold" in new and float(new["threshold"]) > cur["threshold"])
                  or any(k in new and cur[k] and not new[k] for k in ("confirm_new", "confirm_loans", "notify_all")))
        if looser:
            raise PermissionError("Ослабить правила можно только с согласия доверенного лица")
    if "threshold" in new:
        tc.amount_threshold = max(0.0, float(new["threshold"]))
    for k in ("confirm_new", "confirm_loans", "notify_all"):
        if k in new:
            setattr(tc, k, bool(new[k]))
    db.commit()
    return tc


def by_key(db: Session, key: str | None) -> TrustedContact | None:
    if not key:
        return None
    for tc in db.query(TrustedContact).filter(TrustedContact.status == "active"):
        if relative_key(tc.id) == key:
            return tc
    return None


def by_chat(db: Session, chat_id: int | None) -> list[TrustedContact]:
    if chat_id is None:
        return []
    return db.query(TrustedContact).filter(TrustedContact.telegram_chat_id == chat_id,
                                           TrustedContact.status == "active").all()


def transfer_rules(contacts: list[TrustedContact], amount: float, new_person: bool) -> list[dict]:
    """Reasons why the family rules ask for a confirmation of this transfer (empty: rules don't require it)."""
    if not contacts:
        return []
    fmt = lambda x: f"{x:,.0f}".replace(",", " ") + " ₸"
    out = []
    th = min(c.amount_threshold for c in contacts)
    if amount >= th:
        out.append({"code": "family_amount", "points": 0, "ru": f"Сумма от {fmt(th)}: по правилу семьи нужно подтверждение",
                    "kk": f"{fmt(th)} бастап сома: отбасы ережесі бойынша растау қажет"})
    if new_person and any(c.confirm_new for c in contacts):
        out.append({"code": "family_new", "points": 0, "ru": "Новый получатель: по правилу семьи нужно подтверждение",
                    "kk": "Жаңа алушы: отбасы ережесі бойынша растау қажет"})
    return out
