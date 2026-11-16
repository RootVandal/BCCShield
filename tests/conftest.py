import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="bcc_shield_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["OPENAI_API_KEY"] = ""          # tests always run in keyword-only mode
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["SCENARIO_DELAY"] = "0.01"
os.environ["BACKGROUND_ACTIVITY"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
