"""Transfer risk rules. Each returns (points, ru, kk) or None — every point is explainable."""
from dataclasses import dataclass, field
from datetime import datetime

from app.graph.scoring import DROP_THRESHOLD, LINKED_THRESHOLD
from app.models import Account, CallSession, Client, Loan


@dataclass
class Ctx:
    client: Client
    amount: float
    recipient: Account
    now: datetime
    call: CallSession | None = None
    loan: Loan | None = None
    history: list[float] = field(default_factory=list)
    known_recipient: bool = False
    has_signal: bool = False
    pasted: bool = False
    fill_seconds: float | None = None
    kind: str = "transfer"            # transfer / cash / deposit
    telecom: bool = False             # the mobile operator reported a suspicious call right now
    call_scheme: str | None = None    # scheme recognised in the current call (context for the relative)


# what the operation is called in reasons: (ru, kk)
OPS = {"transfer": ("Перевод", "Аударым"), "cash": ("Снятие наличных", "Қолма-қол ақша алу"),
       "deposit": ("Закрытие депозита", "Депозитті жабу")}


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def call_line(call: CallSession, client: Client) -> tuple[str, str]:
    """«Идёт звонок с риском 96%» for a checked conversation, «Идёт звонок: незнакомый номер, 12 мин…» for a phone call."""
    from app.call_guard import context
    p = _pct(call.risk_score)
    if call.source == "phone" and not (call.speech_risk or 0) >= 0.5:
        ru, kk = context.describe(call, client)
        return f"Идёт звонок: {ru} (риск {p})", f"Қоңырау жүріп жатыр: {kk} (қауіп {p})"
    return f"Идёт звонок с риском мошенничества {p}", f"Алаяқтық қаупі {p} қоңырау жүріп жатыр"


def call_risk(c: Ctx):
    if not c.call:
        return None
    if c.call.risk_score >= 0.5:
        ru, kk = call_line(c.call, c.client)
        return round(55 * c.call.risk_score), ru, kk
    ru, kk = OPS[c.kind]
    return 8, f"{ru} во время активного звонка", f"Қоңырау кезіндегі әрекет: {kk.lower()}"


def recent_loan(c: Ctx):
    if not c.loan:
        return None
    minutes = (c.now - c.loan.created_at).total_seconds() / 60
    if minutes <= 30 and c.amount >= 0.7 * c.loan.amount:
        m = max(1, round(minutes))
        return (30, f"Кредит оформлен {m} мин назад, перевод ≥ 70% его суммы",
                f"Несие {m} мин бұрын рәсімделді, аударым оның 70%-нан көп")
    return None


def new_recipient(c: Ctx):
    if c.known_recipient or c.kind != "transfer":
        return None
    return 15, "Новый получатель — раньше переводов не было", "Жаңа алушы — бұрын аударым болмаған"


def unusual_amount(c: Ctx):
    if c.kind == "deposit":  # the amount is the whole deposit, comparing it with transfers says nothing
        return None
    if len(c.history) < 3:
        return (10, "Мало истории переводов для сравнения", "Салыстыруға аударым тарихы аз") if c.amount >= 200_000 else None
    hs = sorted(c.history)
    p95 = hs[min(len(hs) - 1, int(0.95 * len(hs)))]
    mean = sum(hs) / len(hs)
    if c.amount > max(p95, 3 * mean):
        x = c.amount / mean
        return (15, f"Сумма нетипична: в {x:.0f} раз больше обычной", f"Сома әдеттегіден {x:.0f} есе көп")
    return None


def night_time(c: Ctx):
    if 0 <= c.now.hour < 6:
        return 10, "Ночное время (00:00–06:00)", "Түнгі уақыт (00:00–06:00)"
    return None


def _people(n: int) -> str:
    return "человек" if n % 10 not in (2, 3, 4) or n % 100 in (12, 13, 14) else "человека"


def recipient_story(r: Account) -> tuple[str, str] | None:
    """What the graph knows about the card, in words a son can read in Telegram (not «риск графа 87»)."""
    f, fl = r.features or {}, r.flags or {}
    if fl.get("confirmed_drop"):
        return ("Перевод на эту карту уже отклонила семья другого клиента БЦК",
                "Бұл картаға аударымды БЦК-ның басқа клиентінің отбасы қабылдамаған")
    senders = f.get("bcc_senders") if r.is_external else f.get("uniq_senders_7d")
    strangers = round((senders or 0) * (f.get("stranger_share") or 0))
    if strangers >= 3:
        when = "" if r.is_external else " за неделю"
        under = round(100 * (f.get("under_call_share") or 0))
        tail = f", {under}% — во время телефонного звонка" if under >= 30 else ""
        return (f"На эту карту{when} переводили {strangers} незнакомых владельцу {_people(strangers)}{tail}",
                f"Бұл картаға {strangers} бейтаныс адам ақша аударған")
    return None


def risky_recipient(c: Ctx):
    if c.kind != "transfer":
        return None
    r, fl = c.recipient, c.recipient.flags or {}
    if fl.get("antifraud") or c.has_signal:
        return 40, "Получатель в базе Антифрод-центра", "Алушы Антифрод-орталығының базасында"
    if fl.get("frozen"):
        return 40, "Счёт получателя заморожен аналитиком", "Алушының шоты бұғатталған"
    if r.risk_score >= DROP_THRESHOLD:
        story = recipient_story(r)
        if story:
            return 30, f"Получатель похож на дроппера: {story[0][0].lower()}{story[0][1:]}", f"Алушы дроппер сияқты: {story[1]}"
        return (30, f"Получатель связан с дроп-сетью (риск графа {r.risk_score:.0f})",
                f"Алушы дроп-желімен байланысты (граф қаупі {r.risk_score:.0f})")
    if r.risk_score >= LINKED_THRESHOLD:
        return 15, "Получатель имеет подозрительные связи в графе", "Алушының графта күдікті байланыстары бар"
    return None


def cash_out(c: Ctx):
    """Scammers moved to cash: «снимите и передайте курьеру на хранение», «купите доллары»."""
    if c.kind != "cash":
        return None
    if c.amount >= 300_000:
        return (25, "Крупное снятие наличных: мошенники перешли на курьеров и «хранение» денег",
                "Қолма-қол ақшаны ірі сомамен алу: алаяқтар курьерлер мен «сақтауға» көшті")
    if c.amount >= 100_000:
        return 10, "Снятие наличных крупнее обычного", "Әдеттегіден ірі қолма-қол ақша алу"
    return None


def deposit_early(c: Ctx):
    if c.kind != "deposit":
        return None
    return (25, "Досрочное закрытие депозита — частый первый шаг схем «безопасный счёт» и «курьер»",
            "Депозитті мерзімінен бұрын жабу — «қауіпсіз шот» пен «курьер» схемаларының жиі алғашқы қадамы")


def telecom_signal(c: Ctx):
    if not c.telecom:
        return None
    return (45, "Оператор связи: клиенту сейчас звонят с номера из базы мошенников («Телеком Антифрод»)",
            "Байланыс операторы: клиентке қазір алаяқтар базасындағы нөмірден қоңырау шалуда («Телеком Антифрод»)")


def remote_app(c: Ctx):
    """AnyDesk / RustDesk open on the phone. With a phone call on, this is already inside the call's risk."""
    if not c.client.remote_app or (c.call and c.call.source == "phone"):
        return None
    return (30, f"На телефоне открыт удалённый доступ ({c.client.remote_app})",
            f"Телефонда қашықтан қол жеткізу ашық ({c.client.remote_app})")


def elderly(c: Ctx):
    if c.client.age >= 60:
        return 5, "Клиент 60+ (повышенная защита)", "Клиент 60+ (күшейтілген қорғау)"
    return None


def pasted(c: Ctx):
    if c.pasted:
        return 5, "Реквизиты вставлены из буфера обмена", "Деректемелер буферден қойылды"
    return None


def rushed(c: Ctx):
    if c.fill_seconds is not None and c.fill_seconds < 5:
        return 5, f"Форма заполнена за {c.fill_seconds:.0f} сек — спешка", f"Форма {c.fill_seconds:.0f} сек ішінде толтырылды"
    return None


RULES = {
    "call_risk": call_risk,
    "telecom_signal": telecom_signal,
    "remote_app": remote_app,
    "cash_out": cash_out,
    "deposit_early": deposit_early,
    "recent_loan": recent_loan,
    "risky_recipient": risky_recipient,
    "new_recipient": new_recipient,
    "unusual_amount": unusual_amount,
    "night_time": night_time,
    "elderly": elderly,
    "pasted": pasted,
    "rushed": rushed,
}
