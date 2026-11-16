from app.db import SessionLocal
from app.graph import scoring
from app.models import Account
from app.seed import seed


def test_generated_droppers_rank_on_top():
    info = seed()
    assert 300 <= info["accounts"] <= 600
    assert 3000 <= info["transfers"] <= 6000
    with SessionLocal() as db:
        m = scoring.metrics(db)
        assert m["recall"] >= 0.8, m
        assert m["precision"] >= 0.6, m
        accs = sorted(db.query(Account).all(), key=lambda a: -a.risk_score)
        gt = sum(1 for a in accs if (a.flags or {}).get("gt_drop"))
        top = accs[:gt]
        hit = sum(1 for a in top if (a.flags or {}).get("gt_drop"))
        assert hit / gt >= 0.8


def test_external_nodes_scored_and_explained():
    with SessionLocal() as db:
        kaspi = db.query(Account).filter_by(card_key="kaspi:4417").one()
        assert kaspi.is_external
        assert kaspi.risk_score >= scoring.LINKED_THRESHOLD
        assert kaspi.features["reasons"]


def test_propagation_from_confirmed():
    with SessionLocal() as db:
        l1 = next(a for a in db.query(Account).all()
                  if (a.flags or {}).get("network") == 3 and (a.flags or {}).get("gt_drop") and not a.is_external)
        before = {a.id: a.risk_score for a in db.query(Account).all()}
        l1.flags = {**l1.flags, "confirmed_drop": True}
        db.commit()
        scoring.compute(db)
        raised = [a for a in db.query(Account).all() if a.risk_score > before[a.id] + 1 and a.id != l1.id]
        assert raised, "downstream accounts should get propagated risk"
