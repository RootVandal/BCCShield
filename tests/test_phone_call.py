"""Call context without audio: what CallKit / TelephonyCallback tell the bank app is enough to stop the money."""
from fastapi.testclient import TestClient

from app.main import app
from app.security import relative_key

ADMIN = {"X-Admin-Key": "test-admin-key"}
RELATIVE = {"X-Relative-Key": relative_key(1)}


def phone(c, **kw):
    return c.post("/api/clients/1/phone-call", json={"state": "start", **kw}).json()


def test_long_call_from_a_stranger_stops_the_money_and_tells_the_family():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        with c.websocket_connect("/ws") as ws:
            snap = phone(c, caller="+7 701 555 45 67", caller_kind="unknown", minutes_ago=12)
            assert snap["source"] == "phone" and snap["level"] == "medium", snap
            assert {f["code"] for f in snap["context"]} == {"caller_unknown", "call_long", "app_during_call"}
            assert "12 мин" in snap["phone"]["summary"]["ru"]
            alert = None
            for _ in range(40):
                m = ws.receive_json()
                if m["type"] == "relative_alert":
                    alert = m["data"]
                    break
            assert alert and alert["source"] == "phone" and alert["level"] == "medium", alert

        # no word of the conversation was analysed, yet the loan waits for the son
        loan = c.post("/api/clients/1/loans", json={"amount": 1_500_000}).json()
        assert loan["status"] == "pending_relative", loan
        reason = next(r for r in loan["reasons"] if r["code"] == "call_risk")
        assert "незнакомый номер" in reason["ru"]

        r = c.post("/api/clients/1/transfers", json={"bank": "Kaspi", "card": "4400430122334417",
                                                     "amount": 2_000_000, "behavior": {"fill_seconds": 3}}).json()
        assert r["action"] == "pending_relative", r
        assert r["assessment"]["level"] == "high"

        me = c.get("/api/relative/me", headers=RELATIVE).json()["wards"][0]
        assert any(a["source"] == "phone" for a in me["alerts"])


def test_remote_access_makes_it_red():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        phone(c, caller="", caller_kind="unknown", minutes_ago=12)
        c.post("/api/clients/1/remote-access", json={"app": "AnyDesk"})
        snap = next(x for x in c.get("/api/calls/active").json() if x["client_id"] == 1)
        assert snap["level"] == "high", snap
        assert c.get("/api/clients/1").json()["protection_mode"] == "on"
        c.post("/api/clients/1/remote-access", json={"app": None})
        c.post("/api/clients/1/phone-call", json={"state": "end"})
        assert c.get("/api/calls/active").json() == []


def test_son_calling_is_not_a_risk():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        snap = phone(c, caller="Айдар (сын)", caller_kind="contact", minutes_ago=20)
        assert snap["risk"] <= 0.05 and snap["level"] == "low", snap
        r = c.post("/api/clients/1/transfers", json={"bank": "BCC", "phone": "+7 701 555 12 02", "amount": 40_000,
                                                     "behavior": {"fill_seconds": 25}}).json()
        assert r["action"] == "completed", r


def test_short_call_from_a_courier_stays_quiet():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        snap = phone(c, caller="", caller_kind="unknown", minutes_ago=1)
        assert snap["level"] == "low", snap


def test_speakerphone_check_adds_to_the_phone_call():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        snap = phone(c, caller="", caller_kind="unknown", minutes_ago=6)
        ctx = snap["risk"]
        # the speakerphone check attaches to the same call instead of opening a second one
        same = c.post("/api/calls", json={"client_id": 1}).json()
        assert same["call_id"] == snap["call_id"]
        ev = c.post(f"/api/calls/{snap['call_id']}/text", json={"text": "переведите деньги на безопасный счёт"}).json()
        assert ev["risk"] > ctx and ev["speech_risk"] > 0
