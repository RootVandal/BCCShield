from app.db import SessionLocal, reset_db
from app.graph import scoring
from app.graph.generator import generate


def seed(seed: int = 42) -> dict:
    reset_db()
    with SessionLocal() as db:
        info = generate(db, seed=seed)
        info["graph"] = scoring.compute(db)
    return info


if __name__ == "__main__":
    import json

    print(json.dumps(seed(), ensure_ascii=False, indent=2))
