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
    # Without a decision a paused transfer goes through after this many seconds (24 h in a real bank).
    # 300 s for the stage: a trusted contact who is slow to press a button does not let the money go in front of the jury.
    cooling_seconds: int = int(os.getenv("COOLING_SECONDS", "300"))
    scenario_delay: float = float(os.getenv("SCENARIO_DELAY", "2.5"))
    background_activity: bool = os.getenv("BACKGROUND_ACTIVITY", "1") == "1"
    # Access control (see app/security.py). Empty values are generated once and kept in data/secrets.json.
    admin_key: str = os.getenv("ADMIN_KEY", "").strip()
    secret_key: str = os.getenv("SECRET_KEY", "").strip()
    # Public address of the demo (https://bcc.example.com): used in the links the Telegram bot sends.
    public_url: str = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
