import json
from typing import Any, Dict, Optional
import httpx
from fastapi import HTTPException
from app.core.config import settings


WEBHOOK_TIMEOUT_SECONDS = 10


async def emit_webhook(url: str, payload: Dict[str, Any]) -> None:
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
            await client.post(url, json=payload, headers={"Content-Type": "application/json"})
    except Exception:
        # never break the main flow because of webhook delivery issues
        pass


async def emit_payment_success_webhook(db_session_factory, order_group_id: str, payment_ref: str, amount: str) -> None:
    url = getattr(settings, "PAYMENT_SUCCESS_WEBHOOK_URL", None)
    if not url:
        return

    # minimal safe payload; enrich if needed from DB in background worker
    payload = {
        "event": "payment.success",
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "data": {
            "order_id": order_group_id,
            "payment_reference": payment_ref,
            "amount": amount,
            "currency": "KES",
        },
    }
    await emit_webhook(url, payload)
