import uuid

from app.core.db import async_session_maker
from app.features.billing import service
from app.features.notifications.service import send_email


async def send_invoice_receipt(ctx: dict, invoice_id: str) -> None:
    async with async_session_maker() as session:
        result = await service.get_user_for_invoice(session, uuid.UUID(invoice_id))
        if result is None:
            return
        invoice, user = result
        if user is None:
            return
        amount = invoice.amount_paid / 100
        await send_email(
            session,
            to=user.email,
            subject="Your payment receipt",
            html=(
                f"<p>We received your payment of "
                f"{amount:.2f} {invoice.currency.upper()}.</p>"
                + (
                    f'<p><a href="{invoice.hosted_invoice_url}">View invoice</a></p>'
                    if invoice.hosted_invoice_url
                    else ""
                )
            ),
            template="receipt",
        )
