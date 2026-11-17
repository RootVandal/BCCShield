from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

if settings.database_url.startswith("sqlite:///"):
    Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release: existing demo databases (yours, the server's) get them on start.
# Values for old rows keep the old behaviour (the seeded contact stays active and is not phone-checked).
UPGRADES = {
    "trusted_contacts": {
        "status": "VARCHAR(16) DEFAULT 'active'", "confirm_new": "BOOLEAN DEFAULT 1", "confirm_loans": "BOOLEAN DEFAULT 0",
        "notify_all": "BOOLEAN DEFAULT 1", "verify_phone": "BOOLEAN DEFAULT 0", "created_at": "DATETIME",
    },
    "loans": {"status": "VARCHAR(16) DEFAULT 'approved'", "decided_by": "VARCHAR(32)", "cooling_until": "DATETIME",
              "reasons": "JSON DEFAULT '[]'"},
    "clients": {"deposit": "FLOAT DEFAULT 0", "telecom_alert_until": "DATETIME", "remote_app": "VARCHAR(24)"},
    "call_sessions": {"source": "VARCHAR(12) DEFAULT 'speaker'", "caller": "VARCHAR(40) DEFAULT ''",
                      "caller_kind": "VARCHAR(12) DEFAULT ''", "incoming": "BOOLEAN DEFAULT 1",
                      "context_risk": "FLOAT DEFAULT 0", "speech_risk": "FLOAT DEFAULT 0"},
    "transfers": {"kind": "VARCHAR(16) DEFAULT 'transfer'"},
}


def upgrade_schema() -> list[str]:
    from sqlalchemy import inspect, text

    added = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in UPGRADES.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for col, ddl in cols.items():
                if col not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                    added.append(f"{table}.{col}")
    return added


def reset_db():
    from app import models  # noqa: F401  (register tables)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
