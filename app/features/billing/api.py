from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_async_session
from app.features.billing import service
from app.features.billing.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PlanRead,
    SubscriptionRead,
)
from app.features.billing.stripe_client import construct_event
from app.features.users.dependencies import current_active_user
from app.features.users.models import User

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanRead])
async def list_plans(session: AsyncSession = Depends(get_async_session)):
    return await service.list_active_plans(session)


@router.get("/subscription", response_model=SubscriptionRead | None)
async def my_subscription(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    return await service.get_subscription_for_user(session, user)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    try:
        url = await service.create_checkout_session(
            session,
            user=user,
            price_id=payload.price_id,
            success_url=settings.stripe_success_url,
            cancel_url=settings.stripe_cancel_url,
        )
    except Exception as exc:  # noqa: BLE001 - surface Stripe errors as 400
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return CheckoutResponse(url=url)


@router.post("/webhook")
async def webhook(request: Request, session: AsyncSession = Depends(get_async_session)):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = construct_event(payload, signature)
    except Exception as exc:  # noqa: BLE001 - invalid signature/payload
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature") from exc

    created = await service.record_event(session, event["id"], event["type"], payload)
    if not created:
        return {"status": "duplicate"}

    follow_up = await service.handle_event(session, event)
    await service.mark_event_processed(session, event["id"])

    if follow_up and follow_up.get("invoice_id"):
        pool = getattr(request.app.state, "arq_pool", None)
        if pool is not None:
            await pool.enqueue_job("send_invoice_receipt", follow_up["invoice_id"])

    return {"status": "ok"}
