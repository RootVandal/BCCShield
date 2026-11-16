"""Speech-to-text via OpenAI. Language is auto-detected (ru/kk)."""
import logging

from app.config import settings

log = logging.getLogger(__name__)


class STTUnavailable(Exception):
    pass


async def transcribe(data: bytes, filename: str = "chunk.webm") -> str:
    if not settings.llm_enabled:
        raise STTUnavailable("OPENAI_API_KEY не задан — распознавание речи недоступно, используйте ручной ввод или сценарии")
    from app.call_guard.llm import _get_client

    try:
        resp = await _get_client().audio.transcriptions.create(
            model=settings.openai_stt_model, file=(filename, data)
        )
        return (resp.text or "").strip()
    except Exception as e:
        log.warning("STT failed: %s", e)
        raise STTUnavailable(f"Ошибка распознавания: {e}") from e
