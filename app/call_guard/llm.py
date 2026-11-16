"""Layer 2: optional LLM verdict. Returns None when no key or on any error."""
import json
import logging

from app.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты антифрод-аналитик казахстанского банка. Тебе дают фрагмент телефонного разговора
(реплики собеседника клиента, русский или казахский язык, возможны ошибки распознавания речи).
Оцени вероятность, что это мошенничество с социальной инженерией (звонок «из службы безопасности»,
«безопасный счёт», оформление кредита, просьба кодов, удалённый доступ, «родственник в беде», инвестиции и т.п.).
Обычные звонки (врач, доставка без просьбы кодов, родственник) — низкая вероятность.
Ответь строго JSON без пояснений вокруг:
{"is_scam_probability": число 0..1,
 "scheme": "safe_account|fake_loan|relative_in_trouble|investment|delivery|none|other",
 "explanation_ru": "1-2 предложения по-русски",
 "explanation_kk": "1-2 сөйлем қазақша",
 "red_flags": ["короткие признаки"]}"""

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=10)
    return _client


async def analyze_text(text: str) -> dict | None:
    if not settings.llm_enabled or not text.strip():
        return None
    try:
        resp = await _get_client().chat.completions.create(
            model=settings.openai_llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
        )
        data = json.loads(resp.choices[0].message.content)
        data["is_scam_probability"] = max(0.0, min(1.0, float(data.get("is_scam_probability", 0))))
        data.setdefault("scheme", "other")
        data.setdefault("red_flags", [])
        return data
    except Exception as e:  # network, quota, bad JSON — fall back to keywords only
        log.warning("LLM analysis failed: %s", e)
        return None
