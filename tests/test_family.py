"""Several trusted contacts, invitations, family rules, loans, new demo accounts and the Telegram Mini App login."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.family import contacts, linking
from app.main import app
from app.models import TrustedContact
from app.security import relative_key

ADMIN = {"X-Admin-Key": "test-admin-key"}


def rk(contact_id: int) -> dict:
    return {"X-Relative-Key": relative_key(contact_id)}


def new_client(c, name="Гульнар Ибраева", phone="+7 705 100 20 30", balance=900_000) -> dict:
    r = c.post("/api/clients", json={"name": name, "age": 71, "phone": phone, "balance": balance})
    assert r.status_code == 200, r.text
    return r.json()


def accept_in_telegram(contact: dict, chat_id: int):
    with SessionLocal() as db:
        ok, msg = linking.link_chat(db, chat_id, contact["link_code"])
        assert ok, msg


def test_new_account_onboarding_and_second_contact_needs_approval():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        cl = new_client(c)
        assert cl["contacts"] == [] and cl["shield_enabled"] and cl["phone"] == "+77051002030"
        # first trusted contact: invited right away, code for Telegram is shown to the client
        a = c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Арман", "relation": "сын", "phone": "+7 701 900 11 22"}).json()
        assert a["status"] == "invited" and a["link_code"].startswith("GULNAR-")
        accept_in_telegram(a, 9001)
        st = c.get(f"/api/clients/{cl['id']}").json()
        assert [x["status"] for x in st["contacts"]] == ["active"] and st["contacts"][0]["telegram_linked"]
        # second one: an active trusted contact has to allow it (a scammer could ask to add "a bank employee")
        b = c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Дана", "relation": "дочь", "phone": "+7 702 300 44 55"}).json()
        assert b["status"] == "approval" and "link_code" not in b
        with SessionLocal() as db:
            assert not linking.link_chat(db, 9002, "GULNAR-ZZZZZZZZ")[0]  # wrong code
        assert c.post(f"/api/contacts/{b['id']}/decision", json={"decision": "approve"}).status_code == 403
        assert c.post(f"/api/contacts/{b['id']}/decision", json={"decision": "approve"}, headers=rk(b["id"])).status_code == 403
        assert c.post(f"/api/contacts/{b['id']}/decision", json={"decision": "approve"}, headers=rk(a["id"])).json()["status"] == "invited"
        b = next(x for x in c.get(f"/api/clients/{cl['id']}/contacts").json() if x["id"] == b["id"])
        accept_in_telegram(b, 9002)
        assert len(contacts.active_contacts(SessionLocal(), cl["id"])) == 2
        # the same person cannot be added twice, nor the client herself
        assert c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Арман", "phone": "87019001122"}).status_code == 400
        assert c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Гульнар", "phone": "+77051002030"}).status_code == 400


def test_family_rules_new_recipient_amount_and_feed():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        cl = new_client(c, phone="+7 705 111 22 33")
        a = c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Арман", "phone": "+7 701 900 11 23", "threshold": 100_000}).json()
        accept_in_telegram(a, 9101)
        body = {"bank": "Halyk", "card": "4400 0000 0000 7788", "amount": 20_000, "behavior": {"fill_seconds": 30}}
        r = c.post(f"/api/clients/{cl['id']}/transfers", json=body).json()
        assert r["action"] == "pending_relative", r
        assert "family_new" in {x["code"] for x in r["transfer"]["reasons"]}
        tid = r["transfer"]["id"]
        assert c.post(f"/api/transfers/{tid}/decision", json={"decision": "approve"}, headers=rk(1)).status_code == 403  # Saule's son
        assert c.post(f"/api/transfers/{tid}/decision", json={"decision": "approve"}, headers=rk(a["id"])).json()["status"] == "completed"
        # known recipient now, small amount: goes through and is visible in the relative's feed
        r = c.post(f"/api/clients/{cl['id']}/transfers", json=body).json()
        assert r["action"] == "completed", r
        # above the family threshold: paused even for a known recipient
        r = c.post(f"/api/clients/{cl['id']}/transfers", json={**body, "amount": 150_000}).json()
        assert r["action"] == "pending_relative" and "family_amount" in {x["code"] for x in r["transfer"]["reasons"]}
        w = c.get("/api/relative/me", headers=rk(a["id"])).json()["wards"][0]
        assert w["client"]["id"] == cl["id"] and len(w["transfers"]) == 3
        assert [t["amount"] for t in w["pending"]["transfers"]] == [150_000]
        assert all("link_code" not in x for x in w["client"]["contacts"])


def test_loans_wait_for_the_family_and_rules_can_only_get_stricter_from_the_phone():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        cl = new_client(c, phone="+7 705 222 33 44", balance=100_000)
        a = c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Арман", "phone": "+7 701 900 11 24"}).json()
        accept_in_telegram(a, 9201)
        loan = c.post(f"/api/clients/{cl['id']}/loans", json={"amount": 1_000_000}).json()
        assert loan["status"] == "pending_relative"
        assert c.get(f"/api/clients/{cl['id']}").json()["balance"] == 100_000
        assert c.post(f"/api/loans/{loan['id']}/decision", json={"decision": "approve"}).status_code == 403
        assert c.post(f"/api/loans/{loan['id']}/decision", json={"decision": "reject"}, headers=rk(a["id"])).json()["status"] == "rejected"
        assert c.get(f"/api/clients/{cl['id']}").json()["balance"] == 100_000
        # rules: stricter from the phone is fine, looser needs the trusted contact
        assert c.patch(f"/api/contacts/{a['id']}/rules", json={"threshold": 50_000}).status_code == 200
        assert c.patch(f"/api/contacts/{a['id']}/rules", json={"threshold": 500_000}).status_code == 403
        assert c.patch(f"/api/contacts/{a['id']}/rules", json={"confirm_loans": False}).status_code == 403
        assert c.patch(f"/api/contacts/{a['id']}/rules", json={"confirm_loans": False}, headers=rk(a["id"])).json()["rules"]["confirm_loans"] is False
        # removing an active trusted contact from the phone is not allowed
        assert c.delete(f"/api/clients/{cl['id']}/contacts/{a['id']}").status_code == 403
        # an open invitation can be cancelled by the client
        b = c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Дана", "phone": "+7 702 300 44 56"}).json()
        assert c.delete(f"/api/clients/{cl['id']}/contacts/{b['id']}").json()["status"] == "declined"


def test_no_new_contacts_during_a_scam_call_and_web_accept_is_admin_only():
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        cl = new_client(c, phone="+7 705 333 44 55")
        inv = c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Арман", "phone": "+7 701 900 11 25"}).json()
        assert c.get(f"/api/invites/{inv['link_code']}").json()["client"] == "Гульнар Ибраева"
        assert c.post(f"/api/invites/{inv['link_code']}/accept").status_code == 403
        r = c.post(f"/api/invites/{inv['link_code']}/accept", headers=ADMIN).json()
        assert r["relative"].endswith(relative_key(inv["id"]))
        with SessionLocal() as db:  # a scam call has switched protection mode on (see test_flow for the call itself)
            from app.models import Client
            db.get(Client, cl["id"]).protection_mode = "on"
            db.commit()
        r = c.post(f"/api/clients/{cl['id']}/contacts", json={"name": "Сотрудник банка", "phone": "+7 777 000 00 01"})
        assert r.status_code == 400 and "звонка" in r.json()["detail"]


def init_data(user_id: int, token: str, auth_date: int | None = None, tamper: bool = False) -> str:
    fields = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAE",
              "user": json.dumps({"id": user_id, "first_name": "Арман"}, ensure_ascii=False, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if tamper:
        fields["user"] = fields["user"].replace(str(user_id), str(user_id + 1))
    return urlencode(fields)


def test_mini_app_login_is_signed_by_telegram(monkeypatch):
    with TestClient(app) as c:
        c.post("/api/demo/reset", headers=ADMIN)
        monkeypatch.setattr(settings, "telegram_bot_token", "123456:TEST-TOKEN")
        with SessionLocal() as db:
            tc = contacts.active_contacts(db, 1)[0]
            assert linking.link_chat(db, 4242, tc.link_code)[0]
        good = {"X-Telegram-Init-Data": init_data(4242, "123456:TEST-TOKEN")}
        me = c.get("/api/relative/me", headers=good).json()
        assert me["wards"][0]["client"]["name"] == "Сауле Ахметова"
        for bad in (init_data(4242, "999:OTHER"), init_data(4242, "123456:TEST-TOKEN", tamper=True),
                    init_data(4242, "123456:TEST-TOKEN", auth_date=int(time.time()) - 3 * 86400), "garbage",
                    init_data(5555, "123456:TEST-TOKEN")):
            assert c.get("/api/relative/me", headers={"X-Telegram-Init-Data": bad}).status_code == 403
        # the Mini App can decide on the ward's transfers
        call = c.post("/api/calls", json={"client_id": 1}).json()
        for line in ("Здравствуйте, служба безопасности банка", "переведите деньги на безопасный счет срочно"):
            c.post(f"/api/calls/{call['call_id']}/text", json={"text": line})
        r = c.post("/api/clients/1/transfers", json={"bank": "Kaspi", "card": "4400430122334417", "amount": 900_000,
                                                      "behavior": {"fill_seconds": 3, "pasted": True}}).json()
        tid = r["transfer"]["id"]
        assert c.post(f"/api/transfers/{tid}/decision", json={"decision": "reject"}, headers=good).json()["status"] == "rejected"
        assert c.get(f"/api/transfers/{tid}").json()["decided_by"] == f"relative:{tc.id}"


def test_existing_database_is_upgraded_in_place(tmp_path):
    import sqlalchemy as sa

    from app import db as dbmod

    old = sa.create_engine(f"sqlite:///{tmp_path}/old.db")
    with old.begin() as conn:
        conn.execute(sa.text("CREATE TABLE trusted_contacts (id INTEGER PRIMARY KEY, client_id INT, name TEXT, relation TEXT, "
                             "phone TEXT, telegram_chat_id INT, link_code TEXT, amount_threshold FLOAT)"))
        conn.execute(sa.text("CREATE TABLE loans (id INTEGER PRIMARY KEY, client_id INT, amount FLOAT, created_at DATETIME)"))
        conn.execute(sa.text("INSERT INTO trusted_contacts VALUES (1, 1, 'Айдар', 'сын', '+77015551202', NULL, 'SAULE-ABCDEFGH', 100000)"))
    saved = dbmod.engine
    dbmod.engine = old
    try:
        added = dbmod.upgrade_schema()
    finally:
        dbmod.engine = saved
    assert "trusted_contacts.status" in added and "loans.status" in added
    with old.connect() as conn:
        row = conn.execute(sa.text("SELECT status, confirm_loans, verify_phone FROM trusted_contacts")).one()
    assert tuple(row) == ("active", 0, 0)
