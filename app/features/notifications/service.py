from email.message import EmailMessage

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.notifications.models import EmailLog, EmailStatus


async def _deliver(to: str, subject: str, html: str) -> None:
    if settings.email_backend == "console":
        print(f"\n--- EMAIL to {to} ---\nSubject: {subject}\n{html}\n--- END ---\n")
        return
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content("This message requires an HTML-capable client.")
    message.add_alternative(html, subtype="html")
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_tls,
    )


async def send_email(
    session: AsyncSession,
    *,
    to: str,
    subject: str,
    html: str,
    template: str | None = None,
) -> EmailLog:
    """Deliver an email and persist an audit row in either outcome."""
    log = EmailLog(recipient=to, subject=subject, template=template, status=EmailStatus.pending)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    try:
        await _deliver(to, subject, html)
    except Exception as exc:  # noqa: BLE001 - record any delivery failure
        log.status = EmailStatus.failed
        log.error = str(exc)
    else:
        log.status = EmailStatus.sent
    await session.commit()
    return log
