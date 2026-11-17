"""Combines keyword + LLM layers into a smoothed per-call risk and reacts to thresholds."""
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.call_guard import keywords, llm
from app.config import settings
from app.models import CallSession, Client

MEDIUM, HIGH = 0.5, 0.8
LLM_EVERY_N = 3
WINDOW_SECONDS = 60

SCHEME_LABELS = {
    "safe_account": {"ru": "«безопасный счёт»", "kk": "«қауіпсіз шот»"},
    "fake_loan": {"ru": "«отмена кредита»", "kk": "«несиені тоқтату»"},
    "relative_in_trouble": {"ru": "«родственник в беде»", "kk": "«туысқан қиын жағдайда»"},
    "telecom_egov": {"ru": "оператор → eGov → «вы дроппер»", "kk": "оператор → eGov → «сіз дропперсіз»"},
    "investment": {"ru": "«инвестиции»", "kk": "«инвестиция»"},
    "delivery": {"ru": "«доставка»", "kk": "«жеткізу»"},
    "other": {"ru": "социальная инженерия", "kk": "әлеуметтік инженерия"},
    "none": {"ru": "—", "kk": "—"},
}


@dataclass
class CallState:
    # Transcript lives only in memory and only the last fragments, never persisted.
    fragments: deque = field(default_factory=lambda: deque(maxlen=12))
    categories: dict = field(default_factory=dict)
    phrases: list = field(default_factory=list)
    utterances: int = 0
    llm_score: float | None = None
    llm_verdict: dict | None = None
    score: float = 0.0
    alerted: set = field(default_factory=set)


_states: dict[int, CallState] = {}


def get_state(call_id: int) -> CallState:
    return _states.setdefault(call_id, CallState())


def drop_state(call_id: int):
    _states.pop(call_id, None)


def clear_all():
    _states.clear()


def level_of(score: float) -> str:
    return "high" if score >= HIGH else "medium" if score >= MEDIUM else "low"


def guess_scheme(categories: dict) -> str:
    if "relative_in_trouble" in categories:
        return "relative_in_trouble"
    if "telecom_pretext" in categories or "drop_accusation" in categories:
        return "telecom_egov"
    if "safe_account" in categories:
        return "safe_account"
    if "loan_pressure" in categories:
        return "fake_loan"
    if "credentials" in categories or "impersonation" in categories:
        return "other"
    return "none"


def smooth(prev: float, raw: float) -> float:
    # rise fast, fall slowly: one neutral phrase must not reset the alarm
    if raw >= prev:
        return prev + 0.75 * (raw - prev)
    return prev * 0.95 + raw * 0.05


async def process_text(db: Session, call: CallSession, text: str, source: str = "manual") -> dict:
    st = get_state(call.id)
    text = text.strip()
    matches = keywords.find_matches(text)
    for m in matches:
        st.categories[m.category] = max(st.categories.get(m.category, 0), m.weight)
        if m.phrase not in st.phrases:
            st.phrases.append(m.phrase)
    st.fragments.append((time.time(), text))
    st.utterances += 1
    kw = keywords.keyword_score(st.categories)

    if settings.llm_enabled and (matches or st.utterances % LLM_EVERY_N == 0):
        cutoff = time.time() - WINDOW_SECONDS
        window = "\n".join(t for ts, t in st.fragments if ts >= cutoff) or text
        verdict = await llm.analyze_text(window)
        if verdict:
            st.llm_verdict = verdict
            st.llm_score = verdict["is_scam_probability"]

    raw = 0.5 * kw + 0.5 * st.llm_score if st.llm_score is not None else kw
    st.score = round(smooth(st.score, raw), 3)
    level = level_of(st.score)

    scheme = (st.llm_verdict or {}).get("scheme") or guess_scheme(st.categories)
    call.risk_score = st.score
    call.risk_history = [*call.risk_history, {"t": datetime.now().isoformat(timespec="seconds"), "score": st.score}]
    call.matched_phrases = list(st.phrases)
    call.llm_verdict = st.llm_verdict

    triggered = []
    client = db.get(Client, call.client_id)
    for lvl, thr in (("medium", MEDIUM), ("high", HIGH)):
        if st.score >= thr and lvl not in st.alerted:
            st.alerted.add(lvl)
            triggered.append(lvl)
    if "high" in triggered and client.shield_enabled:
        client.protection_mode = "on"
    db.commit()

    return {
        "call_id": call.id,
        "client_id": call.client_id,
        "source": source,
        "fragment": {"text": text, "segments": keywords.highlight(text, matches)},
        "matches": [{"phrase": m.phrase, "category": m.category,
                     "label": keywords.CATEGORY_LABELS[m.category]} for m in matches],
        "categories": {c: keywords.CATEGORY_LABELS[c] for c in st.categories},
        "kw_score": kw,
        "llm": st.llm_verdict,
        "risk": st.score,
        "level": level,
        "scheme": scheme,
        "scheme_label": SCHEME_LABELS.get(scheme, SCHEME_LABELS["other"]),
        "history": call.risk_history[-60:],
        "triggered": triggered,
        "protection_mode": client.protection_mode,
    }


def call_snapshot(call: CallSession) -> dict:
    st = _states.get(call.id)
    return {
        "call_id": call.id,
        "client_id": call.client_id,
        "status": call.status,
        "risk": call.risk_score,
        "level": level_of(call.risk_score),
        "history": call.risk_history[-60:],
        "matched_phrases": call.matched_phrases,
        "llm": call.llm_verdict,
        "fragments": [t for _, t in st.fragments] if st else [],
        "started_at": call.started_at,
    }
