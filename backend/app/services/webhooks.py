"""Outbound event webhooks (order paid, payment success, delivery status).

The target URL and signing secret come from the admin Automation settings,
falling back to the PAYMENT_SUCCESS_WEBHOOK_URL env var. Each POST carries an
X-Ekshop-Signature header (hex HMAC-SHA256 of the body) when a secret is set.

Sends run in the background so a slow or down receiver never delays the
request that triggered them, such as an M-Pesa callback.
"""
import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.automation import AutomationSettings

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 10

# Keep references so pending sends aren't garbage-collected mid-flight.
_pending: Set[asyncio.Task] = set()


def _webhook_target() -> tuple[Optional[str], Optional[str]]:
    db = SessionLocal()
    try:
        row = db.query(AutomationSettings.webhook_url, AutomationSettings.webhook_secret).first()
    except Exception:
        logger.exception("Could not read automation settings for webhooks")
        row = None
    finally:
        db.close()
    url = (row.webhook_url if row else None) or settings.PAYMENT_SUCCESS_WEBHOOK_URL
    secret = row.webhook_secret if row else None
    return url, secret


async def _post(url: str, secret: Optional[str], payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Ekshop-Signature"] = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
            await client.post(url, content=body, headers=headers)
    except Exception as exc:
        # never break the main flow because of webhook delivery issues
        logger.warning("Webhook to %s failed: %s", url, exc)


async def emit_event(event: str, data: Dict[str, Any]) -> None:
    url, secret = _webhook_target()
    if not url:
        return
    payload = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
    task = asyncio.create_task(_post(url, secret, payload))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def emit_payment_success_webhook(db_session_factory, order_group_id: str, payment_ref: str, amount: str) -> None:
    await emit_event("payment.success", {
        "order_id": order_group_id,
        "payment_reference": payment_ref,
        "amount": amount,
        "currency": "KES",
    })


async def emit_order_paid_webhook(db_session_factory, order_group_id: str) -> None:
    await emit_event("order.paid", {"order_id": order_group_id})


async def emit_delivery_status_webhook(delivery_id: str, status: str, order_id: str | None = None) -> None:
    await emit_event("delivery.status", {"delivery_id": delivery_id, "status": status, "order_id": order_id})
