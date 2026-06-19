import json
from pathlib import Path

import pytest
from app.features.billing import service
from app.features.billing.models import Invoice, Plan, Subscription, WebhookEvent
from app.features.users.models import User
from sqlalchemy import select

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures" / "stripe"


def load_event(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


async def _make_user(db, email="pay@b.com", customer="cus_123") -> User:
    user = User(
        email=email,
        hashed_password="x",
        is_active=True,
        stripe_customer_id=customer,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_record_event_is_idempotent(db):
    payload = b'{"id": "evt_1"}'
    first = await service.record_event(db, "evt_1", "x.test", payload)
    second = await service.record_event(db, "evt_1", "x.test", payload)
    assert first is True
    assert second is False

    rows = (await db.execute(select(WebhookEvent))).scalars().all()
    assert len(rows) == 1


async def test_subscription_upsert_links_user_and_plan(db):
    await _make_user(db)
    db.add(
        Plan(
            stripe_price_id="price_basic",
            name="Basic",
            amount=1999,
            currency="usd",
            interval="month",
        )
    )
    await db.commit()

    event = load_event("subscription_created.json")
    await service.handle_event(db, event)

    sub = (await db.execute(select(Subscription))).scalar_one()
    assert sub.status == "active"
    assert sub.user_id is not None
    assert sub.plan_id is not None

    # Re-applying the same subscription object updates in place (no duplicate).
    event["data"]["object"]["status"] = "past_due"
    await service.handle_event(db, event)
    subs = (await db.execute(select(Subscription))).scalars().all()
    assert len(subs) == 1
    assert subs[0].status == "past_due"


async def test_invoice_paid_records_invoice(db):
    user = await _make_user(db)
    event = load_event("invoice_paid.json")
    follow_up = await service.handle_event(db, event)

    invoice = (await db.execute(select(Invoice))).scalar_one()
    assert invoice.amount_paid == 1999
    assert invoice.user_id == user.id
    assert follow_up == {"invoice_id": str(invoice.id)}


async def test_webhook_endpoint_idempotent_and_enqueues(client, app_with_pool, db, monkeypatch):
    await _make_user(db)
    event = load_event("invoice_paid.json")

    # Bypass signature verification at the endpoint boundary.
    import app.features.billing.api as billing_api

    monkeypatch.setattr(billing_api, "construct_event", lambda payload, sig: event)

    r1 = await client.post("/api/v1/billing/webhook", content=b"{}")
    assert r1.json() == {"status": "ok"}
    r2 = await client.post("/api/v1/billing/webhook", content=b"{}")
    assert r2.json() == {"status": "duplicate"}

    jobs = {job[0] for job in app_with_pool.state.arq_pool.jobs}
    assert "send_invoice_receipt" in jobs
