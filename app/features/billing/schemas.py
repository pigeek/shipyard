import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    amount: int
    currency: str
    interval: str
    stripe_price_id: str


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    plan_id: uuid.UUID | None
    current_period_end: datetime | None
    cancel_at_period_end: bool


class CheckoutRequest(BaseModel):
    price_id: str


class CheckoutResponse(BaseModel):
    url: str
