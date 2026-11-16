from datetime import datetime, timedelta

import pytest

from app.db import SessionLocal
from app.models import Account, CallSession, Client, Loan
from app.risk import engine
from app.seed import seed


@pytest.fixture(scope="module")
def db():
    seed()
    with SessionLocal() as s:
        yield s


def saule(db):
    c = db.get(Client, 1)
    return c, db.query(Account).filter_by(client_id=1).first()


def test_transfer_to_son_is_low(db):
    c, src = saule(db)
    son = db.query(Account).filter_by(client_id=2).first()
    a = engine.evaluate(engine.build_ctx(db, c, src, son, 40_000))
    assert a["level"] == "low", a


def test_loan_then_transfer_is_high(db):
    c, src = saule(db)
    db.add(Loan(client_id=c.id, amount=1_500_000, created_at=datetime.now() - timedelta(minutes=2)))
    db.add(CallSession(client_id=c.id, risk_score=0.92))
    db.commit()
    kaspi = engine.find_or_create_recipient(db, "Kaspi", "4400 4301 2233 4417", None)
    a = engine.evaluate(engine.build_ctx(db, c, src, kaspi, 3_500_000))
    codes = {r["code"] for r in a["reasons"]}
    assert a["level"] == "high"
    assert {"recent_loan", "call_risk", "new_recipient", "risky_recipient"} <= codes


def test_medium_answers_escalate():
    base = {"score": 50, "level": "medium", "reasons": [], "context": {}}
    assert engine.escalate_with_answers(base, {"on_call": False})["level"] == "medium"
    assert engine.escalate_with_answers(base, {"safe_account": True})["level"] == "high"


def test_levels():
    assert engine.level_of(10) == "low"
    assert engine.level_of(55) == "medium"
    assert engine.level_of(85) == "high"
