import asyncio
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app import seed as seed_mod
from app.antifraud import mock_center
from app.call_guard import analyzer, scenarios, stt
from app.config import BASE_DIR, settings
from app.db import SessionLocal, engine, get_db
from app.family import service, telegram_bot
from app.family.linking import ensure_strong_codes
from app.graph import scoring
from app.graph import service as graph_service
from app.graph.generator import SIGNAL_CARD
from app.models import Account, CallSession, Client, Transfer, TrustedContact
from app.risk.engine import find_or_create_recipient
from app.schemas import (AnswerIn, CallStartIn, CallTextIn, DecisionIn, LanguageIn, LoanIn, ScenarioIn, ShieldIn,
                         SignalIn, SimulateSignalIn, TransferIn)
from app.security import admin_key, admin_key_from_env, check_admin, is_relative, relative_key, require_relative
from app.ws import hub

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bcc_shield")
STATIC = BASE_DIR / "static"

relative_alerts: list[dict] = []          # in-memory alert feed for the relative page
scenario_tasks: dict[int, asyncio.Task] = {}


async def cooling_loop():
    while True:
        await asyncio.sleep(2)
        try:
            with SessionLocal() as db:
                await service.tick(db)
        except Exception:
            log.exception("cooling tick failed")


async def background_activity():
    """Small everyday transfers from other demo clients so the analyst feed is alive (all low risk)."""
    rng = random.Random()
    while True:
        await asyncio.sleep(rng.uniform(12, 20))
        try:
            with SessionLocal() as db:
                clients = db.query(Client).filter(Client.id > 2, Client.balance > 50_000).all()
                if not clients:
                    continue
                c = rng.choice(clients)
                src = service.account_of(db, c)
                prev = [t.to_account_id for t in db.query(Transfer).filter_by(from_account_id=src.id, synthetic=True)]
                if not prev:
                    continue
                dst = db.get(Account, rng.choice(prev))
                await service.create_transfer(db, c, dst, float(rng.randrange(2_000, 25_000, 500)),
                                              {"fill_seconds": rng.uniform(12, 40)})
        except Exception:
            log.exception("background activity failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not inspect(engine).has_table("clients"):
        log.info("База пуста — создаю демо-данные")
        seed_mod.seed()
    with SessionLocal() as db:
        if ensure_strong_codes(db):
            log.info("Коды привязки Telegram заменены на одноразовые")
        tc = db.query(TrustedContact).filter_by(client_id=1).first()
    base = settings.public_url or f"http://localhost:{settings.port}"
    log.info("Ключ администратора демо%s: %s", " (из ADMIN_KEY)" if admin_key_from_env() else " (data/secrets.json)",
             admin_key())
    log.info("Аналитик с правами: %s/analyst?key=%s", base, admin_key())
    if tc:
        log.info("Ссылка доверенного лица: %s/relative?rk=%s", base, relative_key(tc.id))
    tasks = [asyncio.create_task(cooling_loop())]
    if settings.background_activity:
        tasks.append(asyncio.create_task(background_activity()))
    bot_task = await telegram_bot.start()
    log.info("BCC Shield (демо): http://localhost:%s  | LLM/STT: %s | Telegram: %s", settings.port,
             "on" if settings.llm_enabled else "off (keywords only)", "on" if bot_task else "off")
    yield
    for t in tasks:
        t.cancel()
    await telegram_bot.stop(bot_task)


app = FastAPI(title="BCC Shield (демо)", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def page(name: str):
    return lambda: FileResponse(STATIC / name)


for route, file in {"/": "index.html", "/client": "client.html", "/relative": "relative.html",
                    "/analyst": "analyst.html"}.items():
    app.get(route, include_in_schema=False)(page(file))


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")


def get_client(db: Session, client_id: int) -> Client:
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(404, "Клиент не найден")
    return c


def bad_request(e: Exception):
    raise HTTPException(400, str(e))


# --- general -----------------------------------------------------------------------------------------
@app.get("/api/config")
def config():
    return {"llm_enabled": settings.llm_enabled, "stt_enabled": settings.llm_enabled,
            "telegram_enabled": telegram_bot.bot is not None, "telegram_bot_username": telegram_bot.bot_username,
            "cooling_seconds": settings.cooling_seconds,
            "demo_client_id": 1}


@app.post("/api/demo/reset", dependencies=[Depends(check_admin)])
async def reset_demo():
    for t in scenario_tasks.values():
        t.cancel()
    scenario_tasks.clear()
    relative_alerts.clear()
    analyzer.clear_all()
    info = await asyncio.to_thread(seed_mod.seed)
    await hub.broadcast("reset", {})
    return info


@app.get("/api/demo/links", dependencies=[Depends(check_admin)])
def demo_links(db: Session = Depends(get_db)):
    """Personal links for the presenter: shown on the start page only to admin / localhost."""
    tc = db.query(TrustedContact).filter_by(client_id=1).first()
    return {"relative": f"/relative?rk={relative_key(tc.id)}" if tc else "/relative",
            "analyst": f"/analyst?key={admin_key()}"}


def trusted_of(db: Session, client_id: int) -> TrustedContact | None:
    return db.query(TrustedContact).filter_by(client_id=client_id).first()


def relative_or_admin(request, db: Session, client_id: int, rk: str | None, ak: str | None):
    tc = trusted_of(db, client_id)
    if tc and is_relative(tc.id, rk):
        return
    check_admin(request, ak)


@app.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db)):
    return service.metrics(db)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive pings from the page
    except WebSocketDisconnect:
        hub.disconnect(ws)


# --- client ------------------------------------------------------------------------------------------
@app.get("/api/clients")
def list_clients(db: Session = Depends(get_db)):
    return [service.client_state(db, c) for c in db.query(Client).all()]


@app.get("/api/clients/{client_id}")
def client_info(client_id: int, db: Session = Depends(get_db)):
    return service.client_state(db, get_client(db, client_id))


@app.post("/api/clients/{client_id}/language")
async def set_language(client_id: int, body: LanguageIn, db: Session = Depends(get_db)):
    c = get_client(db, client_id)
    c.language = body.language
    db.commit()
    await service.push_client(db, c)
    return {"language": c.language}


@app.post("/api/clients/{client_id}/shield")
async def set_shield(client_id: int, body: ShieldIn, db: Session = Depends(get_db)):
    """Turning the shield ON is instant; turning it OFF needs the trusted contact (anti-coercion)."""
    c = get_client(db, client_id)
    if body.enabled:
        c.shield_enabled = True
        db.commit()
        await service.push_client(db, c)
        return {"status": "enabled"}
    tc = db.query(TrustedContact).filter_by(client_id=c.id).first()
    await hub.broadcast("shield_off_request", {"client_id": c.id, "client": c.name, "at": datetime.now()})
    return {"status": "pending", "message": f"Отключение щита требует подтверждения: {tc.name} ({tc.relation}) "
                                             "или ожидания 24 часа. Так мошенник не сможет уговорить вас выключить защиту."}


@app.post("/api/clients/{client_id}/shield/confirm-off")
async def confirm_shield_off(client_id: int, db: Session = Depends(get_db),
                             x_relative_key: str | None = Header(default=None)):
    """Only the trusted contact can switch the shield off (a scammer on the client's phone cannot)."""
    c = get_client(db, client_id)
    tc = trusted_of(db, c.id)
    require_relative(tc.id if tc else None, x_relative_key)
    c.shield_enabled, c.protection_mode = False, "off"
    db.commit()
    await service.push_client(db, c)
    return {"status": "disabled"}


@app.post("/api/clients/{client_id}/protection/off")
async def protection_off(client_id: int, request: Request, db: Session = Depends(get_db),
                         x_relative_key: str | None = Header(default=None),
                         x_admin_key: str | None = Header(default=None)):
    c = get_client(db, client_id)
    relative_or_admin(request, db, c.id, x_relative_key, x_admin_key)
    c.protection_mode = "off"
    db.commit()
    await service.push_client(db, c)
    return {"protection_mode": "off"}


@app.get("/api/clients/{client_id}/transfers")
def client_transfers(client_id: int, db: Session = Depends(get_db)):
    acc = service.account_of(db, get_client(db, client_id))
    rows = (db.query(Transfer).filter((Transfer.from_account_id == acc.id) | (Transfer.to_account_id == acc.id))
            .order_by(Transfer.created_at.desc()).limit(40).all())
    return [{**service.serialize_transfer(db, t), "direction": "out" if t.from_account_id == acc.id else "in"}
            for t in rows]


@app.post("/api/clients/{client_id}/loans")
async def take_loan(client_id: int, body: LoanIn, db: Session = Depends(get_db)):
    loan = await service.take_loan(db, get_client(db, client_id), body.amount)
    return {"id": loan.id, "amount": loan.amount, "created_at": loan.created_at}


@app.post("/api/clients/{client_id}/transfers")
async def make_transfer(client_id: int, body: TransferIn, db: Session = Depends(get_db)):
    c = get_client(db, client_id)
    try:
        to_acc = find_or_create_recipient(db, body.bank, body.card, body.phone)
        return await service.create_transfer(db, c, to_acc, body.amount, body.behavior,
                                             body.answers.model_dump() if body.answers else None)
    except ValueError as e:
        db.rollback()
        bad_request(e)


@app.get("/api/clients/{client_id}/bank-call-check")
def bank_call_check(client_id: int):
    # Stub: in production this would query the bank's outbound-call registry.
    return {"bank_calling": False,
            "ru": "🔴 Банк ЦентрКредит вам сейчас НЕ звонит. Положите трубку.",
            "kk": "🔴 ЦентрКредит банкі сізге қазір қоңырау шалмайды. Тұтқаны қойыңыз."}


# --- transfers / relative ----------------------------------------------------------------------------
@app.get("/api/transfers")
def live_transfers(limit: int = 60, db: Session = Depends(get_db)):
    rows = db.query(Transfer).filter(Transfer.synthetic.is_(False)).order_by(Transfer.id.desc()).limit(limit).all()
    return [service.serialize_transfer(db, t) for t in rows]


@app.get("/api/transfers/{transfer_id}")
def transfer_detail(transfer_id: int, db: Session = Depends(get_db)):
    t = db.get(Transfer, transfer_id) or bad_request(ValueError("Перевод не найден"))
    return service.serialize_transfer(db, t)


@app.post("/api/transfers/{transfer_id}/decision")
async def transfer_decision(transfer_id: int, body: DecisionIn, db: Session = Depends(get_db),
                            x_relative_key: str | None = Header(default=None)):
    """Approve / reject a paused transfer. Only the sender's trusted contact may do this."""
    t = db.get(Transfer, transfer_id) or bad_request(ValueError("Перевод не найден"))
    src = db.get(Account, t.from_account_id)
    tc = trusted_of(db, src.client_id) if src and src.client_id else None
    require_relative(tc.id if tc else None, x_relative_key)
    try:
        return await service.decide(db, t, body.decision, by="relative_web")
    except ValueError as e:
        bad_request(e)


@app.post("/api/transfers/{transfer_id}/false-positive", dependencies=[Depends(check_admin)])
async def false_positive(transfer_id: int, db: Session = Depends(get_db)):
    t = db.get(Transfer, transfer_id) or bad_request(ValueError("Перевод не найден"))
    t.false_positive = True
    db.commit()
    if t.status in service.PAUSED:
        await service.complete(db, t, "analyst_false_positive")
    else:
        await service.push_transfer(db, t)
    return service.serialize_transfer(db, t)


@app.post("/api/cooling/fast-forward", dependencies=[Depends(check_admin)])
async def fast_forward(db: Session = Depends(get_db)):
    return {"released": await service.fast_forward(db)}


@app.get("/api/relative/{client_id}/inbox")
def relative_inbox(client_id: int, db: Session = Depends(get_db), x_relative_key: str | None = Header(default=None)):
    c = get_client(db, client_id)
    tc = trusted_of(db, c.id)
    require_relative(tc.id if tc else None, x_relative_key)
    acc = service.account_of(db, c)
    rows = db.query(Transfer).filter(Transfer.from_account_id == acc.id, Transfer.synthetic.is_(False),
                                     Transfer.risk_level == "high").order_by(Transfer.id.desc()).limit(20).all()
    return {"client": service.client_state(db, c),
            "transfers": [service.serialize_transfer(db, t) for t in rows],
            "alerts": [a for a in relative_alerts if a["client_id"] == client_id][-10:]}


# --- calls -------------------------------------------------------------------------------------------
def get_call(db: Session, call_id: int) -> CallSession:
    call = db.get(CallSession, call_id)
    if not call:
        raise HTTPException(404, "Звонок не найден")
    return call


@app.get("/api/scenarios")
def list_scenarios():
    return scenarios.list_scenarios()


@app.get("/api/calls/active")
def active_calls(db: Session = Depends(get_db)):
    return [analyzer.call_snapshot(c) for c in db.query(CallSession).filter_by(status="active")]


@app.post("/api/calls")
async def start_call(body: CallStartIn, db: Session = Depends(get_db)):
    c = get_client(db, body.client_id)
    call = db.query(CallSession).filter_by(client_id=c.id, status="active").first()
    if not call:
        call = CallSession(client_id=c.id)
        db.add(call)
        db.commit()
    snap = analyzer.call_snapshot(call)
    await hub.broadcast("call_started", snap)
    await service.push_client(db, c)
    return snap


async def handle_text(db: Session, call: CallSession, text: str, source: str) -> dict:
    if call.status != "active":
        raise HTTPException(409, "Звонок уже завершён")
    event = await analyzer.process_text(db, call, text, source)
    await hub.broadcast("call_update", event)
    client = db.get(Client, call.client_id)
    if "high" in event["triggered"]:
        tc = db.query(TrustedContact).filter_by(client_id=client.id).first()
        alert = {"id": len(relative_alerts) + 1, "client_id": client.id, "client": client.name,
                 "phone": client.phone, "scheme": event["scheme_label"], "risk": event["risk"],
                 "call_id": call.id, "at": datetime.now(),
                 "relation": tc.relation if tc else None}
        relative_alerts.append(alert)
        await hub.broadcast("relative_alert", alert)
        await telegram_bot.send_call_alert(tc, client, event["scheme_label"]["ru"])
    if event["triggered"]:
        await service.push_client(db, client)
        await hub.broadcast("metrics", service.metrics(db))
    return event


@app.post("/api/calls/{call_id}/text")
async def call_text(call_id: int, body: CallTextIn, db: Session = Depends(get_db)):
    return await handle_text(db, get_call(db, call_id), body.text, "manual")


@app.post("/api/calls/{call_id}/audio")
async def call_audio(call_id: int, file: UploadFile, db: Session = Depends(get_db)):
    call = get_call(db, call_id)
    data = await file.read()
    if len(data) < 1500:
        return {"skipped": True, "reason": "empty chunk"}
    try:
        text = await stt.transcribe(data, file.filename or "chunk.webm")
    except stt.STTUnavailable as e:
        raise HTTPException(503, str(e))
    if not text:
        return {"skipped": True, "reason": "silence"}
    return await handle_text(db, call, text, "mic")


async def run_scenario(call_id: int, name: str):
    data = scenarios.load_scenario(name)
    await hub.broadcast("scenario", {"call_id": call_id, "name": name, "title": data["title"], "state": "started"})
    for line in data["lines"]:
        await asyncio.sleep(settings.scenario_delay)
        with SessionLocal() as db:
            call = db.get(CallSession, call_id)
            if not call or call.status != "active":
                return
            await handle_text(db, call, line, "scenario")
    await hub.broadcast("scenario", {"call_id": call_id, "name": name, "state": "finished"})


@app.post("/api/calls/{call_id}/scenario")
async def call_scenario(call_id: int, body: ScenarioIn, db: Session = Depends(get_db)):
    get_call(db, call_id)
    try:
        scenarios.load_scenario(body.name)
    except KeyError:
        raise HTTPException(404, "Сценарий не найден")
    if call_id in scenario_tasks:
        scenario_tasks[call_id].cancel()
    scenario_tasks[call_id] = asyncio.create_task(run_scenario(call_id, body.name))
    return {"started": body.name}


@app.post("/api/calls/{call_id}/end")
async def end_call(call_id: int, body: AnswerIn | None = None, db: Session = Depends(get_db)):
    call = get_call(db, call_id)
    if call_id in scenario_tasks:
        scenario_tasks.pop(call_id).cancel()
    call.status, call.ended_at = "ended", datetime.now()
    db.commit()
    analyzer.drop_state(call_id)  # forget transcript fragments
    snap = analyzer.call_snapshot(call)
    snap["outcome"] = body.outcome if body else "ended"
    await hub.broadcast("call_ended", snap)
    await service.push_client(db, db.get(Client, call.client_id))
    await hub.broadcast("metrics", service.metrics(db))
    return snap


# --- graph / analyst ---------------------------------------------------------------------------------
@app.get("/api/graph")
def graph(min_risk: float = 40, db: Session = Depends(get_db)):
    return graph_service.graph_view(db, min_risk)


@app.get("/api/graph/account/{account_id}")
def graph_account(account_id: int, db: Session = Depends(get_db)):
    if not db.get(Account, account_id):
        raise HTTPException(404, "Счёт не найден")
    return graph_service.account_detail(db, account_id)


@app.get("/api/graph/chain/{account_id}")
def graph_chain(account_id: int, db: Session = Depends(get_db)):
    return graph_service.chain(db, account_id)


@app.post("/api/graph/recompute", dependencies=[Depends(check_admin)])
async def graph_recompute(db: Session = Depends(get_db)):
    m = scoring.compute(db)
    await hub.broadcast("graph_updated", {})
    return m


@app.post("/api/accounts/{account_id}/freeze", dependencies=[Depends(check_admin)])
async def freeze_account(account_id: int, db: Session = Depends(get_db)):
    a = db.get(Account, account_id) or bad_request(ValueError("Счёт не найден"))
    a.flags = {**(a.flags or {}), "frozen": True, "confirmed_drop": True}
    db.commit()
    scoring.compute(db)
    await hub.broadcast("graph_updated", {"focus": a.id, "reason": "frozen"})
    await hub.broadcast("metrics", service.metrics(db))
    return {"frozen": True}


@app.post("/api/antifraud/signal", dependencies=[Depends(check_admin)])
async def antifraud_signal(body: SignalIn, db: Session = Depends(get_db)):
    a = db.get(Account, body.account_id) or bad_request(ValueError("Счёт не найден"))
    sig = mock_center.send_signal(db, a, body.reason)
    data = mock_center.serialize(db, sig)
    await hub.broadcast("antifraud_signal", data)
    return data


@app.get("/api/antifraud/signals")
def antifraud_journal(db: Session = Depends(get_db)):
    return mock_center.journal(db)


@app.post("/api/antifraud/simulate-incoming", dependencies=[Depends(check_admin)])
async def simulate_incoming(body: SimulateSignalIn | None = None, db: Session = Depends(get_db)):
    if body and body.account_id:
        a = db.get(Account, body.account_id)
    else:
        a = db.query(Account).filter_by(card_key=f"{SIGNAL_CARD[0].lower()}:{SIGNAL_CARD[1]}").first()
    if not a:
        raise HTTPException(404, "Счёт не найден")
    res = mock_center.receive_signal(db, a)
    scoring.compute(db)
    await hub.broadcast("antifraud_signal", res["signal"])
    await hub.broadcast("graph_updated", {"focus": a.id, "reason": "antifraud_in"})
    for c in res["warned_clients"]:
        await hub.broadcast("client_warning", {
            "client_id": c["id"], "card": f"{a.bank} {a.card_mask}",
            "ru": f"Карта {a.bank} {a.card_mask}, на которую вы переводили деньги, отмечена Антифрод-центром как мошенническая. "
                  "Если вас просят перевести ещё — это обман. Позвоните в банк по номеру на карте.",
            "kk": f"Сіз ақша аударған {a.bank} {a.card_mask} картасы Антифрод-орталығында алаяқтық деп белгіленді. "
                  "Тағы аудару сұралса — бұл алдау."})
    await hub.broadcast("metrics", service.metrics(db))
    return {**res, "account_id": a.id}
