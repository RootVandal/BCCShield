"""Decoy mode: when someone else is looking at the client's screen, show him what he expects.

In the remote-access scheme («установите AnyDesk, мы защитим ваш счёт») the scammer watches the client's phone
himself. A «Перевод заблокирован» screen only tells him to switch tactics: another bank, cash, a courier. So while
a remote-access app is open and the shield is on, a risky transfer *looks* sent and a loan *looks* credited, but:

- no money leaves and no loan is issued;
- the recipient card is frozen on the spot and reported to the Antifraud Centre;
- every next card he dictates («первый не дошёл, переведите сюда») is caught the same way;
- the family hears about it at once, and the client sees the truth as soon as the remote access is closed.

Only the screen is staged; the bank's records, the family and the analyst always see what really happened.
"""
from sqlalchemy.orm import Session

from app.antifraud import mock_center
from app.family import telegram_bot
from app.graph import scoring
from app.models import Account, Client, Loan, Transfer
from app.ws import hub

ACTIVE = "decoy"          # caught, the screen still shows success
DONE = "decoy_done"       # remote access closed, the client was told the truth


def active(client: Client) -> bool:
    return bool(client.shield_enabled and client.remote_app)


def applies(client: Client, kind: str, level: str, to_acc: Account) -> bool:
    """A risky transfer (or one to a frozen card) made while a stranger watches the screen."""
    return kind == "transfer" and active(client) and (level != "low" or (to_acc.flags or {}).get("frozen"))


def reason(client: Client) -> dict:
    return {"code": "decoy", "points": 0,
            "ru": f"Приманка: экран видит посторонний ({client.remote_app}), мошеннику показан «перевод выполнен»",
            "kk": f"Жем: экранды бөгде адам көреді ({client.remote_app}), алаяққа «аударым орындалды» көрсетілді"}


async def catch_transfer(db: Session, client: Client, t: Transfer, dst: Account) -> int:
    """Hold the money, freeze the card, report it. Returns how many cards this decoy has caught so far."""
    t.status, t.decided_by = ACTIVE, "decoy"
    dst.flags = {**(dst.flags or {}), "frozen": True, "confirmed_drop": True, "decoy": True,
                 "complaints": int((dst.flags or {}).get("complaints", 0)) + 1}
    db.commit()
    sig = mock_center.send_signal(db, dst, f"Приманка: перевод под удалённым доступом ({client.remote_app}), карта заморожена",
                                  {"transfer_id": t.id, "amount": t.amount})
    scoring.compute(db)
    caught = caught_cards(db, client)
    await hub.broadcast("antifraud_signal", mock_center.serialize(db, sig))
    await hub.broadcast("graph_updated", {"focus": dst.id, "reason": "decoy"})
    await hub.broadcast("decoy", {"client_id": client.id, "client": client.name, "card": f"{dst.bank} {dst.card_mask}",
                                  "amount": t.amount, "cards": caught, "app": client.remote_app})
    await telegram_bot.notify_decoy(db, client, t.amount, f"{dst.bank} {dst.card_mask}", len(caught))
    return len(caught)


def catch_loan(client: Client, loan: Loan):
    loan.status, loan.decided_by = ACTIVE, "decoy"
    loan.reasons = [{"code": "decoy", "ru": f"Приманка: экран видит посторонний ({client.remote_app}), мошеннику показан "
                                           "«кредит зачислен», деньги не выданы",
                     "kk": "Жем: алаяққа «несие түсті» көрсетілді, ақша берілмеді"}] + (loan.reasons or [])


def _source(db: Session, client: Client) -> Account:
    return db.query(Account).filter_by(client_id=client.id).first()


def caught_cards(db: Session, client: Client) -> list[str]:
    acc = _source(db, client)
    rows = db.query(Transfer).filter(Transfer.from_account_id == acc.id, Transfer.status == ACTIVE).all()
    seen = []
    for t in rows:
        d = db.get(Account, t.to_account_id)
        label = f"{d.bank} {d.card_mask}"
        if label not in seen:
            seen.append(label)
    return seen


def state(db: Session, client: Client) -> dict:
    """What the client screen must show while the decoy is on: the balance as the scammer expects it."""
    acc = _source(db, client)
    sent = db.query(Transfer).filter(Transfer.from_account_id == acc.id, Transfer.status == ACTIVE).all()
    loans = db.query(Loan).filter(Loan.client_id == client.id, Loan.status == ACTIVE).all()
    return {"active": active(client) and bool(sent or loans), "armed": active(client),
            "sent": sum(t.amount for t in sent), "loans": sum(l.amount for l in loans),
            "transfer_ids": [t.id for t in sent], "cards": caught_cards(db, client)}


async def reveal(db: Session, client: Client) -> dict | None:
    """Remote access closed: nobody else sees the screen, tell the client what really happened."""
    acc = _source(db, client)
    sent = db.query(Transfer).filter(Transfer.from_account_id == acc.id, Transfer.status == ACTIVE).all()
    loans = db.query(Loan).filter(Loan.client_id == client.id, Loan.status == ACTIVE).all()
    if not sent and not loans:
        return None
    cards = caught_cards(db, client)
    for x in [*sent, *loans]:
        x.status = DONE
    db.commit()
    info = {"client_id": client.id, "amount": sum(t.amount for t in sent), "loans": sum(l.amount for l in loans),
            "cards": cards}
    await hub.broadcast("decoy_reveal", info)
    return info
