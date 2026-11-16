import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_llm_model: str = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
    openai_stt_model: str = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'bcc_shield.db'}")
    cooling_seconds: int = int(os.getenv("COOLING_SECONDS", "60"))
    scenario_delay: float = float(os.getenv("SCENARIO_DELAY", "2.5"))
    background_activity: bool = os.getenv("BACKGROUND_ACTIVITY", "1") == "1"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
