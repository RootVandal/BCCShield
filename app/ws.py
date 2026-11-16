"""Tiny WebSocket hub: every page subscribes and filters events by type."""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import WebSocket

log = logging.getLogger(__name__)


def _default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(type(o))


class Hub:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.discard(ws)

    async def broadcast(self, type_: str, data: dict):
        msg = json.dumps({"type": type_, "data": data}, default=_default, ensure_ascii=False)
        dead = []
        for ws in list(self.connections):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def fire(self, type_: str, data: dict):
        """Broadcast from sync code running inside the event loop."""
        try:
            asyncio.get_running_loop().create_task(self.broadcast(type_, data))
        except RuntimeError:
            pass  # no loop (e.g. some tests) — nothing to notify


hub = Hub()
