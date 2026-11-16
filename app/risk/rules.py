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


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def call_risk(c: Ctx):
    if not c.call:
        return None
    if c.call.risk_score >= 0.5:
        p = _pct(c.call.risk_score)
        return (round(55 * c.call.risk_score), f"Идёт звонок с риском мошенничества {p}",
                f"Алаяқтық қаупі {p} қоңырау жүріп жатыр")
    return 8, "Перевод во время активного звонка", "Қоңырау кезіндегі аударым"


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
    if c.known_recipient:
        return None
    return 15, "Новый получатель — раньше переводов не было", "Жаңа алушы — бұрын аударым болмаған"


def unusual_amount(c: Ctx):
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


def risky_recipient(c: Ctx):
    r, fl = c.recipient, c.recipient.flags or {}
    if fl.get("antifraud") or c.has_signal:
        return 40, "Получатель в базе Антифрод-центра", "Алушы Антифрод-орталығының базасында"
    if fl.get("frozen"):
        return 40, "Счёт получателя заморожен аналитиком", "Алушының шоты бұғатталған"
    if r.risk_score >= DROP_THRESHOLD:
        return (30, f"Получатель связан с дроп-сетью (риск графа {r.risk_score:.0f})",
                f"Алушы дроп-желімен байланысты (граф қаупі {r.risk_score:.0f})")
    if r.risk_score >= LINKED_THRESHOLD:
        return 15, "Получатель имеет подозрительные связи в графе", "Алушының графта күдікті байланыстары бар"
    return None


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
    "recent_loan": recent_loan,
    "risky_recipient": risky_recipient,
    "new_recipient": new_recipient,
    "unusual_amount": unusual_amount,
    "night_time": night_time,
    "elderly": elderly,
    "pasted": pasted,
    "rushed": rushed,
}
