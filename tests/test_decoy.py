"""Decoy mode: with AnyDesk open the scammer sees success, the bank keeps the money and catches every card."""
from fastapi.testclient import TestClient

from app.main import app
from app.security import relative_key

ADMIN = {"X-Admin-Key": "test-admin-key"}
RELATIVE = {"X-Relative-Key": relative_key(1)}
SCAM = {"bank": "Kaspi", "card": "4400430122334417", "amount": 2_000_000, "behavior": {"fill_seconds": 3, "pasted": True}}


def test_scammer_sees_success_money_stays_and_every_card_is_caught():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        before = c.get("/api/clients/1").json()["balance"]
        c.post("/api/clients/1/phone-call", json={"state": "start", "caller_kind": "unknown", "minutes_ago": 12})
        c.post("/api/clients/1/remote-access", json={"app": "AnyDesk"})

        loan = c.post("/api/clients/1/loans", json={"amount": 1_500_000}).json()
        assert loan["status"] == "decoy", loan

        r = c.post("/api/clients/1/transfers", json=SCAM).json()
        assert r["action"] == "decoy", r
        assert r["shown"]["status"] == "completed"          # what the screen shows
        assert r["transfer"]["status"] == "decoy"           # what really happened
        assert r["cards_caught"] == 1

        # «первый перевод не дошёл, переведите на другую карту»
        r2 = c.post("/api/clients/1/transfers", json={**SCAM, "bank": "Halyk", "card": "4405620099990001",
                                                      "amount": 500_000}).json()
        assert r2["action"] == "decoy" and r2["cards_caught"] == 2

        state = c.get("/api/clients/1").json()
        assert state["balance"] == before                    # no money left, no loan issued
        assert state["decoy"]["active"] and state["decoy"]["sent"] == 2_500_000
        assert state["decoy"]["loans"] == 1_500_000
        assert len(state["decoy"]["cards"]) == 2

        # both cards are frozen and reported
        journal = c.get("/api/antifraud/signals").json()
        assert sum("Приманка" in s["payload"]["reason"] for s in journal) == 2
        assert c.get("/api/metrics").json()["decoy_cards"] == 2

        # remote access closed: the client is told the truth
        res = c.post("/api/clients/1/remote-access", json={"app": None}).json()
        assert res["revealed"]["amount"] == 2_500_000 and len(res["revealed"]["cards"]) == 2
        assert not c.get("/api/clients/1").json()["decoy"]["active"]


def test_no_decoy_without_remote_access_and_low_risk_passes():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        c.post("/api/clients/1/remote-access", json={"app": "AnyDesk"})
        # a usual transfer to the son is not staged even with AnyDesk open
        r = c.post("/api/clients/1/transfers", json={"bank": "BCC", "phone": "+7 701 555 12 02", "amount": 40_000,
                                                     "behavior": {"fill_seconds": 25}}).json()
        assert r["action"] != "decoy", r
        c.post("/api/clients/1/remote-access", json={"app": None})
        r = c.post("/api/clients/1/transfers", json=SCAM).json()
        assert r["action"] != "decoy"
