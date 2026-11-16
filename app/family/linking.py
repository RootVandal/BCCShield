"""Linking the trusted contact's Telegram chat, and checking who may answer a transfer request.

Kept free of aiogram so it can be tested without a bot or network.
"""
import time
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from app.models import Account, Transfer, TrustedContact
from app.security import is_strong_link_code, new_link_code

MAX_FAILS = 5            # wrong codes per chat ...
FAIL_WINDOW = 10 * 60    # ... within this many seconds
_fails: dict[int, deque] = defaultdict(deque)


def _blocked(chat_id: int, now: float) -> bool:
    q = _fails[chat_id]
    while q and now - q[0] > FAIL_WINDOW:
        q.popleft()
    return len(q) >= MAX_FAILS


def link_chat(db: Session, chat_id: int, code: str, now: float | None = None) -> tuple[bool, str]:
    """Bind a Telegram chat to the trusted contact owning `code`. The code works once."""
    now = time.time() if now is None else now
    if _blocked(chat_id, now):
        return False, "Слишком много неверных кодов. Попробуйте через 10 минут."
    code = (code or "").strip().upper()
    tc = db.query(TrustedContact).filter_by(link_code=code).first() if code else None
    if tc and tc.telegram_chat_id == chat_id:
        return True, f"Вы уже подключены как доверенное лицо ({tc.relation})."
    if not tc or tc.telegram_chat_id is not None:
        # Unknown code, or the code was already used by another chat: re-binding is not possible from the
        # client's phone (that is exactly what a scammer controlling it would try).
        _fails[chat_id].append(now)
        return False, ("Код не подходит или уже использован. Возьмите актуальную команду в приложении клиента: "
                       "«Щит» → «Подключить Telegram родственника».")
    tc.telegram_chat_id = chat_id
    db.commit()
    _fails.pop(chat_id, None)
    return True, (f"✅ Вы подключены как доверенное лицо ({tc.relation}). "
                  "Сюда будут приходить предупреждения и запросы на подтверждение переводов.")


def chat_may_decide(db: Session, chat_id: int, t: Transfer) -> bool:
    """Only the chat linked to the sender's trusted contact may approve or reject the transfer."""
    src = db.get(Account, t.from_account_id)
    if not src or not src.client_id:
        return False
    tc = db.query(TrustedContact).filter_by(client_id=src.client_id).first()
    return bool(tc and tc.telegram_chat_id is not None and tc.telegram_chat_id == chat_id)


def ensure_strong_codes(db: Session) -> int:
    """Upgrade old weak demo codes (SAULE-7341) in an existing database to one-time strong ones."""
    n = 0
    for tc in db.query(TrustedContact).filter(TrustedContact.telegram_chat_id.is_(None)):
        if not is_strong_link_code(tc.link_code):
            prefix = (tc.link_code or "SAULE").rsplit("-", 1)[0] or "SAULE"
            tc.link_code = new_link_code(prefix)
            n += 1
    if n:
        db.commit()
    return n
