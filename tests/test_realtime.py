"""WebSocket / ASGI-push tests.

These exercise the realtime hub and the notifications surface without a real
WebSocket handshake (Starlette's sync TestClient can't share the suite's
in-memory async SQLite event loop). The hub's fan-out and the REST→push path are
covered with a fake socket; the ``@router.websocket`` accept/receive loop itself
is thin Starlette glue over ``hub.connect``/``disconnect``.
"""

import json
import uuid

import pytest
from app.core.realtime import RealtimeHub, hub
from app.features.notifications.realtime import push_to_user, user_channel

pytestmark = pytest.mark.asyncio


class FakeWebSocket:
    """Minimal stand-in for a Starlette WebSocket the hub can drive."""

    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[str] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


async def test_hub_fans_out_to_local_subscribers():
    h = RealtimeHub()
    a, b = FakeWebSocket(), FakeWebSocket()
    await h.connect("room", a)
    await h.connect("room", b)
    assert a.accepted and b.accepted

    await h.publish("room", {"event": "ping", "data": {"n": 1}})

    assert json.loads(a.sent[0]) == {"event": "ping", "data": {"n": 1}}
    assert json.loads(b.sent[0]) == {"event": "ping", "data": {"n": 1}}


async def test_hub_disconnect_stops_delivery():
    h = RealtimeHub()
    a, b = FakeWebSocket(), FakeWebSocket()
    await h.connect("room", a)
    await h.connect("room", b)

    h.disconnect("room", a)
    await h.publish("room", {"event": "x", "data": {}})

    assert a.sent == []
    assert len(b.sent) == 1


async def test_publish_to_empty_channel_is_noop():
    h = RealtimeHub()
    await h.publish("nobody", {"event": "x", "data": {}})  # must not raise


async def test_echo_endpoint_requires_auth(client):
    r = await client.post("/api/v1/notifications/echo", json={"message": "hi"})
    assert r.status_code == 401


async def test_echo_endpoint_pushes_to_caller_channel(client):
    # Register + log in (cookie auth via the httpx client).
    await client.post(
        "/api/v1/auth/register",
        json={"email": "rt@b.com", "password": "supersecret1"},
    )
    login = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "rt@b.com", "password": "supersecret1"},
    )
    token = login.json()["access_token"]
    me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]

    # Attach a fake socket to this user's channel on the process-wide hub, then
    # echo through the REST surface and assert it arrives.
    channel = user_channel(uuid.UUID(user_id))
    sock = FakeWebSocket()
    await hub.connect(channel, sock)
    try:
        r = await client.post(
            "/api/v1/notifications/echo",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 202
        assert json.loads(sock.sent[0]) == {"event": "echo", "data": {"message": "hello"}}
    finally:
        hub.disconnect(channel, sock)


async def test_push_to_user_helper_roundtrips():
    h_user = uuid.uuid4()
    sock = FakeWebSocket()
    await hub.connect(user_channel(h_user), sock)
    try:
        await push_to_user(h_user, "evt", {"k": "v"})
        assert json.loads(sock.sent[0]) == {"event": "evt", "data": {"k": "v"}}
    finally:
        hub.disconnect(user_channel(h_user), sock)
