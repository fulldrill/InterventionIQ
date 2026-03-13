"""Email delivery helpers for account verification and password reset flows."""
from email.message import EmailMessage
from urllib.parse import quote
import logging

import aiosmtplib

from core.config import settings

logger = logging.getLogger(__name__)


def _verification_link(token: str) -> str:
    # Route through public app URL so links work outside container network.
    safe_token = quote(token, safe="")
    return f"{settings.app_url.rstrip('/')}/api/auth/verify-email?token={safe_token}"


async def send_verification_email(recipient_email: str, token: str) -> None:
    """Send a verification email. Raises on hard SMTP failures."""
    verify_url = _verification_link(token)

    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = recipient_email
    msg["Subject"] = "Verify your InterventionIQ account"
    msg.set_content(
        "\n".join(
            [
                "Welcome to InterventionIQ!",
                "",
                "Please verify your email by opening this link:",
                verify_url,
                "",
                f"This link expires in {settings.email_verify_expire_hours} hour(s).",
            ]
        )
    )

    # Typical ports:
    # - 465: implicit TLS
    # - 587: STARTTLS
    # - 1025: local Mailpit (no TLS/auth)
    use_tls = settings.smtp_port == 465
    start_tls = settings.smtp_port == 587

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=20,
        )
    except Exception as exc:
        # In development, many local SMTP tools do not need auth/TLS.
        if settings.app_env == "development":
            logger.warning("Primary SMTP send failed; retrying without auth/TLS: %s", exc)
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                timeout=20,
            )
            return
        raise
