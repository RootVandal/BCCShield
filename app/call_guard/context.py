"""Call context without audio.

Neither iOS nor Android lets an app hear a phone call, and a bank must not listen to its clients. What any app
does get from the phone is the fact of the call: iOS CallKit (CXCallObserver) says a call is up, incoming or
outgoing, and how long it has lasted; Android (TelephonyCallback) says the same and, with permission, the number,
so the app can tell a contact from a stranger. Add what the bank app sees itself — it was opened in the middle of
the call, a remote-access app is running — and the risk is clear before a single word is analysed.

Every point is explained, the same way as in the transfer rules.
"""
from datetime import datetime

from app.models import CallSession, Client

HIDDEN = 0.10       # number hidden or foreign
UNKNOWN = 0.30      # incoming from a number not in the contacts
LONG = ((10, 0.20), (5, 0.10))   # minutes on the line → points
APP_OPEN = 0.15     # the bank app is opened while the call goes on (the caller walks the client through it)
REMOTE = 0.35       # AnyDesk / RustDesk: someone else may be looking at the screen
CONTACT_CAP = 0.05  # a call from the son is not a risk, whatever else


def minutes(call: CallSession, now: datetime | None = None) -> int:
    return max(0, int(((now or datetime.now()) - call.started_at).total_seconds() // 60))


def factors(call: CallSession | None, client: Client, now: datetime | None = None) -> list[dict]:
    """[{code, points, ru, kk}] — why the context of this call is risky."""
    out = []
    remote = client.remote_app
    if remote:
        out.append({"code": "remote_app", "points": REMOTE,
                    "ru": f"На телефоне открыт удалённый доступ ({remote}): экран может видеть посторонний",
                    "kk": f"Телефонда қашықтан қол жеткізу ашық ({remote}): экранды бөгде адам көруі мүмкін"})
    if not call or call.source != "phone":
        return out
    if call.caller_kind == "contact":
        return out + [{"code": "caller_contact", "points": 0, "ru": f"Звонит контакт: {call.caller}",
                       "kk": f"Контакт қоңырау шалуда: {call.caller}"}]
    if call.incoming:
        out.append({"code": "caller_unknown", "points": UNKNOWN, "ru": "Входящий звонок с номера не из контактов",
                    "kk": "Контактілерде жоқ нөмірден кіріс қоңырау"})
    if call.caller_kind == "hidden":
        out.append({"code": "caller_hidden", "points": HIDDEN, "ru": "Номер скрыт или зарубежный",
                    "kk": "Нөмір жасырын немесе шетелдік"})
    m = minutes(call, now)
    for limit, pts in LONG:
        if m >= limit:
            out.append({"code": "call_long", "points": pts, "ru": f"Разговор идёт уже {m} мин",
                        "kk": f"Әңгіме {m} минуттан бері жүріп жатыр"})
            break
    out.append({"code": "app_during_call", "points": APP_OPEN, "ru": "Приложение банка открыто во время звонка",
                "kk": "Банк қосымшасы қоңырау кезінде ашылды"})
    return out


def risk(call: CallSession | None, client: Client, now: datetime | None = None) -> float:
    fs = factors(call, client, now)
    score = min(0.95, sum(f["points"] for f in fs))
    if call and call.source == "phone" and call.caller_kind == "contact":
        score = min(score, CONTACT_CAP) if not client.remote_app else score
    return round(score, 3)


def combine(context: float, speech: float) -> float:
    """Two independent signals: either one alone can raise the alarm, together they reinforce each other."""
    return round(1 - (1 - context) * (1 - speech), 3)


def describe(call: CallSession, client: Client, now: datetime | None = None) -> tuple[str, str]:
    """One line for the relative and the transfer reasons: «незнакомый номер, 12 мин, приложение банка открыто»."""
    if call.caller_kind == "contact":
        return f"звонит {call.caller}", f"{call.caller} қоңырау шалуда"
    who_ru = "скрытый номер" if call.caller_kind == "hidden" else "незнакомый номер"
    who_kk = "жасырын нөмір" if call.caller_kind == "hidden" else "бейтаныс нөмір"
    m = minutes(call, now)
    ru = f"{who_ru}, {m} мин, приложение банка открыто"
    kk = f"{who_kk}, {m} мин, банк қосымшасы ашық"
    if client.remote_app:
        ru += f", открыт {client.remote_app}"
        kk += f", {client.remote_app} ашық"
    return ru, kk
