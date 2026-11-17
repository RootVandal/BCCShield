"""Access control: the trusted contact and the analyst cannot be impersonated from the client's side."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.family import linking
from app.main import app
from app.models import Transfer, TrustedContact
from app.security import is_strong_link_code, relative_key

ADMIN = {"X-Admin-Key": "test-admin-key"}
RELATIVE = {"X-Relative-Key": relative_key(1)}
SCAM = {"bank": "Kaspi", "card": "4400430122334417", "amount": 900_000, "behavior": {"fill_seconds": 3, "pasted": True}}


def paused_transfer(c) -> int:
    c.post("/api/demo/reset", headers=ADMIN)
    call = c.post("/api/calls", json={"client_id": 1}).json()
    for line in ("Здравствуйте, служба безопасности банка", "переведите деньги на безопасный счет срочно"):
        c.post(f"/api/calls/{call['call_id']}/text", json={"text": line})
    r = c.post("/api/clients/1/transfers", json=SCAM).json()
    assert r["action"] == "pending_relative", r
    return r["transfer"]["id"]


def test_decision_requires_trusted_contact():
    with TestClient(app) as c:
        tid = paused_transfer(c)
        body = {"decision": "approve", "by": "relative_web"}
        assert c.post(f"/api/transfers/{tid}/decision", json=body).status_code == 403
        assert c.post(f"/api/transfers/{tid}/decision", json=body, headers={"X-Relative-Key": "x" * 32}).status_code == 403
        assert c.post(f"/api/transfers/{tid}/decision", json=body, headers=ADMIN).status_code == 403  # not the analyst either
        assert c.get(f"/api/transfers/{tid}").json()["status"] == "pending_relative"
        ok = c.post(f"/api/transfers/{tid}/decision", json={"decision": "reject"}, headers=RELATIVE)
        assert ok.status_code == 200 and ok.json()["status"] == "rejected"
        assert c.get(f"/api/transfers/{tid}").json()["decided_by"] == "relative:1"


def test_shield_off_and_protection_need_relative():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        assert c.post("/api/clients/1/shield/confirm-off", json={}).status_code == 403
        assert c.post("/api/clients/1/protection/off", json={}).status_code == 403
        assert c.get("/api/clients/1").json()["shield_enabled"] is True
        assert c.post("/api/clients/1/shield/confirm-off", json={}, headers=RELATIVE).status_code == 200
        assert c.get("/api/clients/1").json()["shield_enabled"] is False


def test_admin_actions_and_inbox_are_locked():
    with TestClient(app) as c:
        for method, path in (("post", "/api/demo/reset"), ("post", "/api/cooling/fast-forward"),
                             ("post", "/api/graph/recompute"), ("post", "/api/accounts/5/freeze"),
                             ("post", "/api/antifraud/simulate-incoming"), ("get", "/api/demo/links"),
                             ("post", "/api/transfers/1/false-positive")):
            assert getattr(c, method)(path).status_code == 403, path
            assert getattr(c, method)(path, headers={"X-Admin-Key": "wrong"}).status_code == 403, path
        assert c.get("/api/relative/me").status_code == 403
        assert c.get("/api/relative/me", headers={"X-Relative-Key": "0" * 32}).status_code == 403
        assert c.get("/api/relative/me", headers=RELATIVE).status_code == 200
        links = c.get("/api/demo/links", headers=ADMIN).json()
        assert links["relative"].endswith(relative_key(1))
        # reading stays open for the demo
        assert c.get("/api/graph").status_code == 200 and c.get("/api/metrics").status_code == 200


def test_localhost_is_admin_but_proxy_is_not():
    with TestClient(app, client=("127.0.0.1", 5000)) as c:
        assert c.get("/api/demo/links").status_code == 200
        assert c.get("/api/demo/links", headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 403
        assert c.get("/api/demo/links", headers={"CF-Connecting-IP": "203.0.113.7"}).status_code == 403


def test_telegram_link_code_is_strong_one_time_and_rate_limited():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
    with SessionLocal() as db:
        tc = db.query(TrustedContact).filter_by(client_id=1).first()
        code = tc.link_code
        assert is_strong_link_code(code) and code.startswith("SAULE-")
        assert linking.link_chat(db, 111, code.lower())[0] is True          # first chat links (case-insensitive)
        assert linking.link_chat(db, 111, code)[0] is True                  # same chat again: fine
        assert linking.link_chat(db, 222, code)[0] is False                 # another chat cannot steal it
        db.refresh(tc)
        assert tc.telegram_chat_id == 111
        for i in range(10):
            linking.link_chat(db, 333, f"SAULE-WRONG{i:03d}", now=1000 + i)
        ok, msg = linking.link_chat(db, 333, code, now=1011)
        assert not ok and "Слишком много" in msg
        assert linking.link_chat(db, 333, "SAULE-AAAAAAAA", now=1000 + 11 * 60)[1] != msg  # window expired


def test_telegram_decision_only_from_linked_chat():
    with TestClient(app) as c:
        tid = paused_transfer(c)
    with SessionLocal() as db:
        tc = db.query(TrustedContact).filter_by(client_id=1).first()
        linking.link_chat(db, 777, tc.link_code)
        t = db.get(Transfer, tid)
        assert linking.chat_may_decide(db, 777, t)
        assert not linking.chat_may_decide(db, 778, t)


def test_old_weak_codes_are_upgraded():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
    with SessionLocal() as db:
        tc = db.query(TrustedContact).filter_by(client_id=1).first()
        tc.link_code = "SAULE-7341"
        db.commit()
        assert linking.ensure_strong_codes(db) == 1
        db.refresh(tc)
        assert is_strong_link_code(tc.link_code) and tc.link_code != "SAULE-7341"
