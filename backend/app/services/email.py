import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _send(to: str, subject: str, html: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.info("[DEV] Email to %s: %s\n%s", to, subject, html)
        return

    response = httpx.post(
        RESEND_API_URL,
        json={"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": html},
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
    )
    response.raise_for_status()


def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    _send(
        to=to,
        subject="Verify your Ekshop account",
        html=f"""
            <p>Welcome to Ekshop!</p>
            <p><a href="{link}">Click here to verify your email</a> to activate your account.</p>
            <p>This link expires in 24 hours.</p>
        """,
    )


def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    _send(
        to=to,
        subject="Reset your Ekshop password",
        html=f"""
            <p>We received a request to reset your password.</p>
            <p><a href="{link}">Click here to set a new password</a>.</p>
            <p>This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>
        """,
    )
