import time

from fastapi.testclient import TestClient

from app.main import app


def wait_risk(client, call_id, level, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        calls = {c["call_id"]: c for c in client.get("/api/calls/active").json()}
        if calls.get(call_id, {}).get("level") == level:
            return calls[call_id]
        time.sleep(0.05)
    raise AssertionError(f"call did not reach {level}: {calls.get(call_id)}")


def test_main_demo_scenario():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        before = c.get("/api/clients/1").json()
        assert before["balance"] == 2_300_000

        with c.websocket_connect("/ws") as ws:
            call = c.post("/api/calls", json={"client_id": 1}).json()
            c.post(f"/api/calls/{call['call_id']}/scenario", json={"name": "scam_security_ru"})
            snap = wait_risk(c, call["call_id"], "high")
            assert snap["risk"] >= 0.8
            types = set()
            for _ in range(40):
                types.add(ws.receive_json()["type"])
                if "relative_alert" in types:
                    break
            assert "relative_alert" in types
        assert c.get("/api/clients/1").json()["protection_mode"] == "on"

        assert c.post("/api/clients/1/loans", json={"amount": 1_500_000}).status_code == 200
        r = c.post("/api/clients/1/transfers", json={"bank": "Kaspi", "card": "4400430122334417",
                                                     "amount": 3_500_000, "behavior": {"fill_seconds": 3}}).json()
        assert r["action"] == "pending_relative", r
        codes = {x["code"] for x in r["assessment"]["reasons"]}
        assert {"recent_loan", "call_risk", "new_recipient", "risky_recipient"} <= codes
        tid = r["transfer"]["id"]

        inbox = c.get("/api/relative/1/inbox").json()
        assert any(t["id"] == tid and t["status"] == "pending_relative" for t in inbox["transfers"])

        assert c.post(f"/api/transfers/{tid}/decision", json={"decision": "reject"}).json()["status"] == "rejected"
        after = c.get("/api/clients/1").json()
        assert after["balance"] == 2_300_000 + 1_500_000  # money stays

        signals = c.get("/api/antifraud/signals").json()
        assert signals and signals[0]["payload"]["card"] == "•• 4417"
        m = c.get("/api/metrics").json()
        assert m["saved"] == 3_500_000 and m["stopped"] == 1
        kaspi_id = r["transfer"]["to"]["id"]
        acc = c.get(f"/api/graph/account/{kaspi_id}").json()
        assert acc["confirmed"] and acc["risk"] >= 85
        assert len(acc["chain"]["nodes"]) > 3


def test_normal_call_and_transfer_do_not_interfere():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        for name in ("normal_doctor", "normal_delivery", "normal_son"):
            call = c.post("/api/calls", json={"client_id": 1}).json()
            c.post(f"/api/calls/{call['call_id']}/scenario", json={"name": name})
            time.sleep(0.6)
            snap = next(x for x in c.get("/api/calls/active").json() if x["call_id"] == call["call_id"])
            assert snap["level"] == "low", (name, snap)
            c.post(f"/api/calls/{call['call_id']}/end", json={"outcome": "ended"})
        r = c.post("/api/clients/1/transfers", json={"bank": "BCC", "phone": "+7 701 555 12 02", "amount": 40_000,
                                                     "behavior": {"fill_seconds": 20}}).json()
        assert r["action"] == "completed", r
        assert r["assessment"]["level"] == "low"


def test_medium_questions_and_cooling():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        body = {"bank": "Halyk", "card": "4405 6200 1111 7788", "amount": 250_000, "behavior": {"pasted": True}}
        r = c.post("/api/clients/1/transfers", json=body).json()
        assert r["action"] == "questions", r
        r = c.post("/api/clients/1/transfers", json={**body, "answers": {"on_call": True}}).json()
        assert r["action"] == "pending_relative"
        c.post("/api/cooling/fast-forward")
        t = c.get(f"/api/transfers/{r['transfer']['id']}").json()
        assert t["status"] == "completed" and t["decided_by"] == "cooling_expired"


def test_incoming_antifraud_signal_and_no_keys_mode():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        cfg = c.get("/api/config").json()
        assert cfg["llm_enabled"] is False
        call = c.post("/api/calls", json={"client_id": 1}).json()
        resp = c.post(f"/api/calls/{call['call_id']}/audio", files={"file": ("a.webm", b"x" * 4000, "audio/webm")})
        assert resp.status_code == 503
        r = c.post("/api/antifraud/simulate-incoming").json()
        assert r["signal"]["direction"] == "in"
        assert any(w["name"] == "Гульнара Ибраева" for w in r["warned_clients"])
