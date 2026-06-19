import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.models import Invoice, Plan, Subscription, WebhookEvent
from app.features.billing.stripe_client import get_stripe
from app.features.users.models import User
from app.features.users.service import get_user_by_id


class BillingError(Exception):
    """Expected, user-facing billing failure."""


# --- Plans -----------------------------------------------------------------


async def list_active_plans(session: AsyncSession) -> list[Plan]:
    result = await session.execute(
        select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.amount)
    )
    return list(result.scalars())


async def get_plan_by_price(session: AsyncSession, price_id: str) -> Plan | None:
    result = await session.execute(select(Plan).where(Plan.stripe_price_id == price_id))
    return result.scalar_one_or_none()


# --- Customer + checkout ---------------------------------------------------


async def ensure_customer(session: AsyncSession, user: User) -> str:
    """Return the user's Stripe customer id, creating it on first use."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = get_stripe().Customer.create(email=user.email, metadata={"user_id": str(user.id)})
    user.stripe_customer_id = customer["id"]
    await session.commit()
    return user.stripe_customer_id


async def create_checkout_session(
    session: AsyncSession, *, user: User, price_id: str, success_url: str, cancel_url: str
) -> str:
    customer_id = await ensure_customer(session, user)
    checkout = get_stripe().checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": str(user.id)},
    )
    return checkout["url"]


async def get_subscription_for_user(session: AsyncSession, user: User) -> Subscription | None:
    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


# --- Webhook idempotency + handling ----------------------------------------


async def record_event(
    session: AsyncSession, event_id: str, event_type: str, payload: bytes | str | None
) -> bool:
    """Insert the event ledger row. Returns False if already seen (duplicate)."""
    raw = payload.decode() if isinstance(payload, bytes) else payload
    session.add(WebhookEvent(stripe_event_id=event_id, type=event_type, payload=raw))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def mark_event_processed(session: AsyncSession, event_id: str) -> None:
    result = await session.execute(
        select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is not None:
        event.processed = True
        await session.commit()


def _to_datetime(timestamp: int | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


async def _resolve_user_id(
    session: AsyncSession, customer_id: str | None, metadata: dict | None
) -> uuid.UUID | None:
    if metadata and metadata.get("user_id"):
        try:
            return uuid.UUID(str(metadata["user_id"]))
        except ValueError:
            pass
    if customer_id:
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user is not None:
            return user.id
    return None


async def upsert_subscription(session: AsyncSession, sub: dict) -> Subscription:
    """Create or update a Subscription from a Stripe subscription object."""
    result = await session.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == sub["id"])
    )
    record = result.scalar_one_or_none()

    items = sub.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = await get_plan_by_price(session, price_id) if price_id else None
    user_id = await _resolve_user_id(session, sub.get("customer"), sub.get("metadata"))

    if record is None:
        record = Subscription(
            stripe_subscription_id=sub["id"],
            stripe_customer_id=sub.get("customer", ""),
            user_id=user_id,
        )
        session.add(record)

    if user_id is not None:
        record.user_id = user_id
    record.plan_id = plan.id if plan else record.plan_id
    record.status = sub.get("status", record.status)
    record.current_period_end = _to_datetime(sub.get("current_period_end"))
    record.cancel_at_period_end = bool(sub.get("cancel_at_period_end", False))
    await session.commit()
    await session.refresh(record)
    return record


async def record_invoice(session: AsyncSession, invoice: dict) -> Invoice:
    result = await session.execute(
        select(Invoice).where(Invoice.stripe_invoice_id == invoice["id"])
    )
    record = result.scalar_one_or_none()
    user_id = await _resolve_user_id(session, invoice.get("customer"), invoice.get("metadata"))
    if record is None:
        record = Invoice(stripe_invoice_id=invoice["id"])
        session.add(record)
    record.user_id = user_id
    record.amount_paid = invoice.get("amount_paid", 0)
    record.currency = invoice.get("currency", "usd")
    record.status = invoice.get("status", "draft")
    record.hosted_invoice_url = invoice.get("hosted_invoice_url")
    await session.commit()
    await session.refresh(record)
    return record


async def handle_event(session: AsyncSession, event: dict) -> dict | None:
    """Apply a Stripe event. Returns a small follow-up descriptor or None."""
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        await upsert_subscription(session, obj)
        return None

    if event_type in {"invoice.paid", "invoice.payment_succeeded"}:
        invoice = await record_invoice(session, obj)
        return {"invoice_id": str(invoice.id)}

    return None


async def get_user_for_invoice(
    session: AsyncSession, invoice_id: uuid.UUID
) -> tuple[Invoice, User | None] | None:
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None:
        return None
    user = await get_user_by_id(session, invoice.user_id) if invoice.user_id else None
    return invoice, user
