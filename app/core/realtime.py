"""In-process + Redis pub/sub hub backing WebSocket fan-out (ASGI push).

An infra seam in the spirit of ``core/storage.py`` and ``core/redis.py``. A
single :class:`RealtimeHub` tracks local WebSocket connections grouped by an
opaque *channel* string and delivers messages published from anywhere in the
app:

- ``realtime_provider="memory"`` (default): delivery is in-process only — perfect
  for the test suite and single-process dev, no infra required.
- ``realtime_provider="redis"``: a background subscriber relays every message
  published on *any* worker to the sockets held by *every* worker, so push works
  across a horizontally-scaled deployment. Redis is already present (arq broker).

Features push via :meth:`publish`; the ``/ws/<feature>`` surface registers
sockets via :meth:`connect` / :meth:`disconnect`. See ``features/notifications``
for the reference implementation.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from starlette.websockets import WebSocket

from app.core.config import settings

_CHANNEL_PREFIX = "rt:"


class RealtimeHub:
    def __init__(self) -> None:
        self._local: dict[str, set[WebSocket]] = {}
        self._redis: Any = None
        self._pubsub: Any = None
        self._reader: asyncio.Task[None] | None = None

    # --- connection registry -------------------------------------------------
    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._local.setdefault(channel, set()).add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        conns = self._local.get(channel)
        if conns is not None:
            conns.discard(websocket)
            if not conns:
                self._local.pop(channel, None)

    # --- publish / dispatch --------------------------------------------------
    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Deliver ``message`` (JSON-serializable) to everyone on ``channel``.

        With Redis the message round-trips through pub/sub so all workers see it
        (including this one, via the subscriber loop) — a single delivery path.
        Without Redis it is dispatched to the local sockets directly.
        """
        raw = json.dumps(message)
        if self._redis is not None:
            await self._redis.publish(_CHANNEL_PREFIX + channel, raw)
        else:
            await self._dispatch_local(channel, raw)

    async def _dispatch_local(self, channel: str, raw: str) -> None:
        for ws in list(self._local.get(channel, ())):
            try:
                await ws.send_text(raw)
            except Exception:  # noqa: BLE001 - a dead socket shouldn't break fan-out
                self.disconnect(channel, ws)

    # --- lifecycle (no-op unless realtime_provider == "redis") ---------------
    async def start(self) -> None:
        if settings.realtime_provider != "redis":
            return
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe(_CHANNEL_PREFIX + "*")
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._pubsub is not None
        async for msg in self._pubsub.listen():
            if msg.get("type") != "pmessage":
                continue
            channel = msg["channel"][len(_CHANNEL_PREFIX) :]
            await self._dispatch_local(channel, msg["data"])

    async def stop(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader
            self._reader = None
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


hub = RealtimeHub()


def get_realtime_hub() -> RealtimeHub:
    """Accessor for the process-wide hub (parallels ``get_storage``)."""
    return hub
