"""REST surface for notifications.

``POST /api/v1/notifications/echo`` is a self-contained demo of ASGI push: it
pushes a message to the caller's own ``/ws/notifications`` channel, so a client
can prove the WebSocket round-trip end to end (open socket → echo → receive).
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.features.notifications.realtime import push_to_user
from app.features.users.dependencies import current_active_user
from app.features.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class EchoRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/echo", status_code=status.HTTP_202_ACCEPTED)
async def echo(
    payload: EchoRequest,
    user: User = Depends(current_active_user),
) -> dict[str, str]:
    await push_to_user(user.id, "echo", {"message": payload.message})
    return {"status": "pushed"}
