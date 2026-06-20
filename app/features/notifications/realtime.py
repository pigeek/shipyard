"""Realtime push helpers for the notifications feature.

A thin domain layer over the generic ``core/realtime`` hub: it owns the channel
naming (one private channel per user) so the rest of the app pushes by user id
without knowing the hub's wire format.
"""

import uuid
from typing import Any

from app.core.realtime import get_realtime_hub


def user_channel(user_id: uuid.UUID) -> str:
    return f"user:{user_id}"


async def push_to_user(user_id: uuid.UUID, event: str, data: dict[str, Any]) -> None:
    """Push ``{"event": ..., "data": ...}`` to every socket a user has open."""
    await get_realtime_hub().publish(user_channel(user_id), {"event": event, "data": data})
