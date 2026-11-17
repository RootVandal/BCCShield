"""Telegram side of trusted contacts: finding an invitation by code (rate-limited) and checking who may decide.

Kept free of aiogram so it can be tested without a bot or network.
"""
import time
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from app.family import contacts
from app.models import Account, Transfer, TrustedContact
from app.security import is_strong_link_code, new_link_code

MAX_FAILS = 5            # wrong codes / numbers per chat ...
FAIL_WINDOW = 10 * 60    # ... within this many seconds
_fails: dict[int, deque] = defaultdict(deque)


def _blocked(chat_id: int, now: float) -> bool:
    q = _fails[chat_id]
    while q and now - q[0] > FAIL_WINDOW:
        q.popleft()
    return len(q) >= MAX_FAILS


def register_fail(chat_id: int, now: float | None = None):
    _fails[chat_id].append(time.time() if now is None else now)


def find_invite(db: Session, chat_id: int, code: str, now: float | None = None) -> tuple[TrustedContact | None, str | None]:
    """Invitation (or a not-yet-linked active contact) by its one-time code. Returns (contact, error)."""
    now = time.time() if now is None else now
    if _blocked(chat_id, now):
        return None, "Слишком много неверных попыток. Попробуйте через 10 минут."
    code = (code or "").strip().upper()
    tc = db.query(TrustedContact).filter_by(link_code=code).first() if code else None
    if tc and tc.telegram_chat_id == chat_id and tc.status == "active":
        return tc, None
    usable = tc and (tc.status == "invited" or (tc.status == "active" and tc.telegram_chat_id is None))
    if not usable:
        # unknown, already used by another chat, waiting for approval, declined or removed: re-binding from the
        # client's phone is not possible (that is exactly what a scammer controlling it would try)
        register_fail(chat_id, now)
        if tc and tc.status == "approval":
            return None, "Это приглашение ещё не одобрено текущим доверенным лицом."
        return None, ("Код не подходит или уже использован. Возьмите актуальное приглашение в приложении близкого: "
                      "«Семейный щит» → доверенное лицо.")
    _fails.pop(chat_id, None)
    return tc, None


def link_chat(db: Session, chat_id: int, code: str, now: float | None = None) -> tuple[bool, str]:
    """Find the invitation and accept it right away (no phone check). Used by tests and the legacy seeded contact."""
    tc, err = find_invite(db, chat_id, code, now)
    if err:
        return False, err
    if tc.telegram_chat_id == chat_id and tc.status == "active":
        return True, f"Вы уже подключены как доверенное лицо ({tc.relation})."
    try:
        contacts.accept(db, tc, chat_id)
    except ValueError as e:
        return False, str(e)
    return True, f"✅ Вы подключены как доверенное лицо ({tc.relation})."


def transfer_client(db: Session, t: Transfer | None) -> int | None:
    if not t:
        return None
    src = db.get(Account, t.from_account_id)
    return src.client_id if src else None


def chat_contact(db: Session, chat_id: int, client_id: int | None) -> TrustedContact | None:
    """The active trusted contact of `client_id` linked to this Telegram chat, if any."""
    if client_id is None:
        return None
    return next((c for c in contacts.by_chat(db, chat_id) if c.client_id == client_id), None)


def chat_may_decide(db: Session, chat_id: int, t: Transfer) -> bool:
    return chat_contact(db, chat_id, transfer_client(db, t)) is not None


def ensure_strong_codes(db: Session) -> int:
    """Upgrade old weak demo codes (SAULE-7341) in an existing database to one-time strong ones."""
    n = 0
    for tc in db.query(TrustedContact).filter(TrustedContact.telegram_chat_id.is_(None),
                                              TrustedContact.status.in_(contacts.LIVE)):
        if not is_strong_link_code(tc.link_code):
            prefix = (tc.link_code or "SAULE").rsplit("-", 1)[0] or "SAULE"
            tc.link_code = new_link_code(prefix)
            n += 1
    if n:
        db.commit()
    return n
