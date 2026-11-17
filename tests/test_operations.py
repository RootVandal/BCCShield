"""Cash withdrawal, early deposit closure, loan freeze under a risky call, «Телеком Антифрод» operator signal."""
from fastapi.testclient import TestClient

from app.main import app
from app.security import relative_key

ADMIN = {"X-Admin-Key": "test-admin-key"}
RELATIVE = {"X-Relative-Key": relative_key(1)}  # Aidar, Saule's trusted contact


def state(c, cid=1):
    return c.get(f"/api/clients/{cid}").json()


def test_cash_withdrawal_goes_through_risk_engine_and_family():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        # small cash: low risk, below the family threshold -> completed at once
        r = c.post("/api/clients/1/operations", json={"kind": "cash", "amount": 50_000}).json()
        assert r["action"] == "completed", r
        assert r["transfer"]["kind"] == "cash" and r["transfer"]["title"] == "Снятие наличных"
        assert state(c)["balance"] == 2_300_000 - 50_000

        # large cash: questions first (medium), then the family decides
        body = {"kind": "cash", "amount": 2_000_000}
        r = c.post("/api/clients/1/operations", json=body).json()
        assert r["action"] == "questions"
        assert "cash_out" in {x["code"] for x in r["assessment"]["reasons"]}
        r = c.post("/api/clients/1/operations", json={**body, "answers": {"on_call": False}}).json()
        assert r["action"] == "pending_relative", r
        assert state(c)["frozen"] == 2_000_000
        tid = r["transfer"]["id"]
        me = c.get("/api/relative/me", headers=RELATIVE).json()["wards"][0]
        assert any(t["id"] == tid and t["kind"] == "cash" for t in me["pending"]["transfers"])

        signals_before = len(c.get("/api/antifraud/signals").json())
        assert c.post(f"/api/transfers/{tid}/decision", json={"decision": "reject"}, headers=RELATIVE).json()["status"] == "rejected"
        assert state(c)["balance"] == 2_250_000          # money stays
        assert len(c.get("/api/antifraud/signals").json()) == signals_before  # the cash desk is not a dropper
        assert c.get("/api/metrics").json()["saved"] == 2_000_000


def test_deposit_closure_free_normally_frozen_under_operator_signal():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        assert state(c)["deposit"] == 4_500_000
        assert c.post("/api/clients/1/telecom-signal", json={}).status_code == 403   # presenter only
        assert c.post("/api/clients/1/telecom-signal", json={}, headers=ADMIN).status_code == 200
        s = state(c)
        assert s["telecom_alert"] and s["protection_mode"] == "on"

        r = c.post("/api/clients/1/operations", json={"kind": "deposit"}).json()
        assert r["action"] == "pending_relative", r
        codes = {x["code"] for x in r["assessment"]["reasons"]}
        assert {"telecom_signal", "deposit_early"} <= codes
        assert state(c)["frozen"] == 0                 # the deposit is not card money
        assert c.post("/api/clients/1/operations", json={"kind": "deposit"}).status_code == 400  # already waiting
        tid = r["transfer"]["id"]
        assert c.post(f"/api/transfers/{tid}/decision", json={"decision": "approve"}, headers=RELATIVE).json()["status"] == "completed"
        s = state(c)
        assert s["deposit"] == 0 and s["balance"] == 2_300_000 + 4_500_000


def test_deposit_closure_without_danger_completes():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        r = c.post("/api/clients/1/operations", json={"kind": "deposit"}).json()
        assert r["action"] == "completed", r
        assert state(c)["deposit"] == 0


def test_loan_is_instant_normally_and_cools_down_when_nobody_to_ask():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        loan = c.post("/api/clients/1/loans", json={"amount": 500_000}).json()
        assert loan["status"] == "approved" and not loan["reasons"]

        # a new client without trusted contacts, in protection mode: nobody to ask -> cooling, then released
        cid = c.post("/api/clients", json={"name": "Гульнар Тестова", "age": 70}).json()["id"]
        c.post(f"/api/clients/{cid}/telecom-signal", json={}, headers=ADMIN)
        loan = c.post(f"/api/clients/{cid}/loans", json={"amount": 300_000}).json()
        assert loan["status"] == "cooling" and loan["cooling_until"], loan
        bal = state(c, cid)["balance"]
        c.post("/api/cooling/fast-forward", headers=ADMIN)
        assert state(c, cid)["balance"] == bal + 300_000
