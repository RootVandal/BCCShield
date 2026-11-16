"""Access control for the demo.

Three roles, matching the threat model "the scammer controls the victim's phone":
- client   — the victim's own app. Open in the demo (the scammer has it anyway).
- relative — the trusted contact. Decides on paused transfers and on turning the shield off.
             Proves itself with a per-contact key (web page) or with the linked Telegram chat.
- admin    — presenter / antifraud analyst: demo reset, analyst actions.
             Allowed without a key only for direct requests from this computer (localhost).

Keys are derived from one server secret, so nothing new is stored in the database.
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
from pathlib import Path

from fastapi import Header, HTTPException, Request

from app.config import settings

log = logging.getLogger(__name__)

# Headers a reverse proxy (Traefik, Cloudflare Tunnel, nginx) adds: such a request is never "local".
PROXY_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip", "cf-connecting-ip")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: easy to read aloud and type


def _data_dir() -> Path:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///")).parent
    return Path(__file__).resolve().parent.parent / "data"


def _load_secrets() -> dict:
    """SECRET_KEY / ADMIN_KEY from the environment, otherwise generated once and kept in data/secrets.json."""
    path = _data_dir() / "secrets.json"
    stored = {}
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    changed = False
    for key in ("secret_key", "admin_key"):
        if not stored.get(key):
            stored[key] = secrets.token_urlsafe(32 if key == "secret_key" else 18)
            changed = True
    if changed:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(stored, indent=2), encoding="utf-8")
        except OSError as e:  # read-only disk: keys live until restart, which is still safe
            log.warning("Не удалось сохранить %s: %s", path, e)
    return {"secret_key": settings.secret_key or stored["secret_key"],
            "admin_key": settings.admin_key or stored["admin_key"],
            "admin_from_env": bool(settings.admin_key)}


_secrets: dict | None = None


def _get() -> dict:
    global _secrets
    if _secrets is None:
        _secrets = _load_secrets()
    return _secrets


def admin_key() -> str:
    return _get()["admin_key"]


def admin_key_from_env() -> bool:
    return _get()["admin_from_env"]


def relative_key(contact_id: int) -> str:
    mac = hmac.new(_get()["secret_key"].encode(), f"relative:{contact_id}".encode(), hashlib.sha256)
    return mac.hexdigest()[:32]


def new_link_code(prefix: str = "SAULE") -> str:
    return f"{prefix}-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def is_strong_link_code(code: str) -> bool:
    tail = (code or "").rsplit("-", 1)[-1]
    return len(tail) >= 8 and all(ch in CODE_ALPHABET for ch in tail)


def is_local(request: Request) -> bool:
    if any(h in request.headers for h in PROXY_HEADERS):
        return False
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _same(a: str | None, b: str) -> bool:
    return bool(a) and hmac.compare_digest(a.encode(), b.encode())


def check_admin(request: Request, x_admin_key: str | None = Header(default=None)):
    """FastAPI dependency: presenter / analyst actions."""
    if is_local(request) or _same(x_admin_key, admin_key()):
        return True
    raise HTTPException(403, "Нужен ключ администратора демо. Откройте страницу по ссылке с ?key=… "
                             "(ключ печатается в логе сервера при запуске).")


def is_relative(contact_id: int | None, key: str | None) -> bool:
    return contact_id is not None and _same(key, relative_key(contact_id))


def require_relative(contact_id: int | None, key: str | None):
    if not is_relative(contact_id, key):
        raise HTTPException(403, "Это действие доступно только доверенному лицу: откройте страницу родственника "
                                 "по персональной ссылке (?rk=…) или ответьте в Telegram-боте.")
