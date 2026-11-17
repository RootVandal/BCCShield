"""Honest measurement of the keyword layer: false alarms on normal calls, detection on scam calls.

Runs every conversation from scenarios/eval/ through the same steps as analyzer.process_text
(find_matches -> keyword_score -> smooth), without the LLM and without the database.
Run `python -m app.eval` for a table.
"""
import json
import sys

from app.call_guard import keywords
from app.call_guard.analyzer import guess_scheme, level_of, smooth
from app.config import BASE_DIR

EVAL_DIR = BASE_DIR / "scenarios" / "eval"


def run_conversation(lines: list[str]) -> dict:
    """Final risk, level and guessed scheme of one call, as the keyword layer sees it."""
    categories: dict[str, float] = {}
    score = 0.0
    for line in lines:
        for m in keywords.find_matches(line.strip()):
            categories[m.category] = max(categories.get(m.category, 0), m.weight)
        score = round(smooth(score, keywords.keyword_score(categories)), 3)
    return {"risk": score, "level": level_of(score), "scheme": guess_scheme(categories)}


def _load(kind: str) -> list[dict]:
    return json.loads((EVAL_DIR / f"{kind}.json").read_text(encoding="utf-8"))


def evaluate() -> dict:
    items = []
    for kind in ("normal", "scam"):
        for conv in _load(kind):
            r = run_conversation(conv["lines"])
            items.append({"title": conv["title"], "kind": kind, "risk": r["risk"], "level": r["level"]})

    def count(kind: str, level: str) -> int:
        return sum(1 for i in items if i["kind"] == kind and i["level"] == level)

    n_normal = sum(1 for i in items if i["kind"] == "normal")
    n_scam = sum(1 for i in items if i["kind"] == "scam")
    nm, nh = count("normal", "medium"), count("normal", "high")
    sm, sh = count("scam", "medium"), count("scam", "high")
    return {
        "normal": {"total": n_normal, "alarms_medium": nm, "alarms_high": nh,
                   "rate": round((nm + nh) / n_normal, 3) if n_normal else 0.0},
        "scam": {"total": n_scam, "detected_high": sh, "detected_medium": sm,
                 "rate": round(sh / n_scam, 3) if n_scam else 0.0},
        "items": items,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = evaluate()
    print(f"{'вид':<7} {'риск':>5}  {'уровень':<7} разговор")
    for i in sorted(res["items"], key=lambda x: (x["kind"], -x["risk"])):
        print(f"{i['kind']:<7} {i['risk']:>5.2f}  {i['level']:<7} {i['title']}")
    n, s = res["normal"], res["scam"]
    print()
    print(f"Обычные разговоры: {n['total']}, ложных тревог medium: {n['alarms_medium']}, "
          f"high: {n['alarms_high']}, доля ложных: {n['rate']:.1%}")
    print(f"Мошеннические: {s['total']}, распознано high: {s['detected_high']}, "
          f"только medium: {s['detected_medium']}, доля high: {s['rate']:.1%}")


if __name__ == "__main__":
    main()
