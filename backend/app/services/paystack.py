import hashlib
import hmac
from decimal import Decimal

import httpx

from app.core.config import settings

PAYSTACK_BASE_URL = "https://api.paystack.co"


def to_subunit(amount: str) -> int:
    """Paystack amounts are in the smallest currency unit (e.g. cents for KES)."""
    return int((Decimal(amount) * 100).to_integral_value())


def initialize_transaction(email: str, amount: str, reference: str, callback_url: str) -> dict:
    response = httpx.post(
        f"{PAYSTACK_BASE_URL}/transaction/initialize",
        json={
            "email": email,
            "amount": to_subunit(amount),
            "currency": "KES",
            "reference": reference,
            "callback_url": callback_url,
        },
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
    )
    response.raise_for_status()
    return response.json()["data"]


def verify_transaction(reference: str) -> dict:
    response = httpx.get(
        f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
    )
    response.raise_for_status()
    return response.json()["data"]


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    if not signature or not settings.PAYSTACK_SECRET_KEY:
        return False
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
