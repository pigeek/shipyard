"""WebSocket surface for live notifications — mounted at ``/ws/notifications``.

This is the reference for the ``ws_router`` surface convention (registry §
FeatureModule). The socket is authenticated with the same revocable JWT as the
REST/SSR surfaces (cookie for browsers, bearer for native clients), subscribes
the connection to the user's private channel, then idles — push is one-way
(server → client) via ``realtime.push_to_user``; inbound frames are ignored.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from app.core.realtime import get_realtime_hub
from app.features.notifications.realtime import user_channel
from app.features.users.dependencies import ws_current_user
from app.features.users.models import User

router = APIRouter()


@router.websocket("/notifications")
async def notifications_ws(
    websocket: WebSocket,
    user: User | None = Depends(ws_current_user),
) -> None:
    if user is None:
        # Reject the handshake before accepting (browser sees a 403).
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    hub = get_realtime_hub()
    channel = user_channel(user.id)
    await hub.connect(channel, websocket)  # accepts the socket
    try:
        while True:
            # Keep the connection open; we don't act on client messages yet.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(channel, websocket)
