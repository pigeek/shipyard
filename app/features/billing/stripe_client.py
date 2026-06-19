import stripe

from app.core.config import settings


def get_stripe() -> "stripe":
    """Return the stripe module configured with the current API key."""
    stripe.api_key = settings.stripe_api_key
    return stripe


def construct_event(payload: bytes, signature: str | None) -> dict:
    """Verify a webhook signature and return the parsed event.

    Isolated here so tests can monkeypatch it without touching the endpoint.
    """
    return get_stripe().Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
