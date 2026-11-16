import json

from app.config import BASE_DIR

SCENARIO_DIR = BASE_DIR / "scenarios"


def list_scenarios() -> list[dict]:
    out = []
    for p in sorted(SCENARIO_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        out.append({"id": p.stem, "title": data["title"], "kind": data.get("kind", "scam"), "lines": len(data["lines"])})
    return out


def load_scenario(name: str) -> dict:
    path = SCENARIO_DIR / f"{name}.json"
    if not path.resolve().is_relative_to(SCENARIO_DIR.resolve()) or not path.exists():
        raise KeyError(name)
    return json.loads(path.read_text(encoding="utf-8"))
