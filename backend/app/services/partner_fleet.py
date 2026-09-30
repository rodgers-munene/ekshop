"""Partner fleet (3PL) integration service.

Handles outbound dispatch to external couriers, inbound webhook verification,
and state reconciliation onto our own Delivery rows.

Credential handling: partner API keys and webhook secrets are encrypted at rest
with the same Fernet key used for message bodies (see app.core.crypto). They are
never returned by the API layer -- schemas expose a boolean `has_api_key` instead.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_message, encrypt_message
from app.models.delivery import (
    Delivery,
    DeliveryStatus,
    PartnerFulfillmentMode,
    PartnerFleet,
    PartnerJob,
    PartnerJobStatus,
    PartnerStatus,
    PartnerWebhookEvent,
)
from app.models.shop import Shop

logger = logging.getLogger(__name__)


class PartnerNotConfigured(RuntimeError):
    """Raised when a partner exists but has no usable credentials/endpoint."""


class PartnerAPIError(RuntimeError):
    """Partner rejected or failed to answer the request."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# ── Credentials ────────────────────────────────────────────────────────────────


def encrypt_api_key(plaintext: str) -> str:
    return encrypt_message(plaintext)


def decrypt_api_key(ciphertext: str) -> str:
    return decrypt_message(ciphertext)


def set_partner_api_key(partner: PartnerFleet, api_key: str) -> None:
    partner.api_key_encrypted = encrypt_message(api_key)


def set_partner_webhook_secret(partner: PartnerFleet, secret: str) -> None:
    partner.webhook_secret_encrypted = encrypt_message(secret)


def _require_credentials(partner: PartnerFleet) -> tuple[str, str | None]:
    if not partner.api_base_url:
        raise PartnerNotConfigured(f"Partner {partner.slug} has no api_base_url configured")
    if not partner.api_key_encrypted:
        raise PartnerNotConfigured(f"Partner {partner.slug} has no API key configured")
    try:
        api_key = decrypt_message(partner.api_key_encrypted)
    except ValueError as exc:
        # Most likely the deployment rotated MESSAGE_ENCRYPTION_KEY.
        raise PartnerNotConfigured(
            f"Partner {partner.slug} API key could not be decrypted: {exc}"
        ) from exc

    webhook_secret = None
    if partner.webhook_secret_encrypted:
        try:
            webhook_secret = decrypt_message(partner.webhook_secret_encrypted)
        except ValueError:
            logger.warning(
                "Partner %s webhook secret could not be decrypted; inbound "
                "callbacks will be rejected until it is re-saved.",
                partner.slug,
            )
    return api_key, webhook_secret


# ── Quoting ────────────────────────────────────────────────────────────────────


def quote_partner_job(
    partner: PartnerFleet,
    *,
    distance_km: float,
    weight_kg: float = 0.0,
) -> Decimal:
    """Compute our cost to hand this job to the partner."""
    km = Decimal(str(distance_km or 0))
    kg = Decimal(str(weight_kg or 0))
    return (
        Decimal(partner.base_pickup_fee or 0)
        + Decimal(partner.per_km_fee or 0) * km
        + Decimal(partner.per_kg_fee or 0) * kg
    ).quantize(Decimal("0.01"))


def estimate_partner_ttl(partner: PartnerFleet, distance_km: float) -> timedelta:
    """Best-effort ETA until the partner reports a driver."""
    if partner.avg_delivery_minutes:
        # 45% of historical transit is dispatch+pickup, the rest is line-haul.
        transit = float(partner.avg_delivery_minutes) * 0.55
    else:
        # ~32 km/h effective city speed, plus a flat 25 min handling allowance.
        transit = (float(distance_km or 0) / 32.0) * 60.0 + 25.0
    return timedelta(minutes=max(15.0, transit))


# ── Payload building ───────────────────────────────────────────────────────────


def _address_payload(address: dict) -> dict:
    """Keep only the fields a courier needs; drop internal geo ids."""
    return {
        "name": f"{address.get('first_name', '')} {address.get('last_name', '')}".strip() or None,
        "phone": address.get("phone"),
        "county": address.get("county"),
        "town": address.get("town"),
        "ward": address.get("ward"),
        "location": address.get("exact_location"),
        "apartment": address.get("apartment"),
        "notes": address.get("notes"),
        "lat": address.get("lat"),
        "lng": address.get("lng"),
    }


def build_job_payload(
    partner: PartnerFleet,
    delivery: Delivery,
    *,
    distance_km: float,
    weight_kg: float = 0.0,
    fulfillment_mode: PartnerFulfillmentMode = PartnerFulfillmentMode.same_city,
) -> dict:
    """Build the dispatch body. Partner-agnostic; partners map it to their API."""
    if delivery.order is None:
        raise PartnerAPIError(f"Delivery {delivery.id} has no order loaded")

    shop: Shop | None = delivery.order.shop
    order_address = delivery.order.delivery_address or {}

    pickup = {
        "name": shop.name if shop else None,
        "phone": shop.phone if shop else None,
        "county": shop.county if shop else None,
        "town": shop.town if shop else None,
        "location": shop.exact_location if shop else None,
        "lat": shop.lat if shop else None,
        "lng": shop.lng if shop else None,
    }

    recipient = {
        "name": f"{order_address.get('first_name', '')} {order_address.get('last_name', '')}".strip() or None,
        "phone": order_address.get("phone"),
        "county": order_address.get("county"),
        "town": order_address.get("town"),
        "ward": order_address.get("ward"),
        "location": order_address.get("exact_location"),
        "apartment": order_address.get("apartment"),
        "notes": order_address.get("notes"),
        "lat": order_address.get("lat"),
        "lng": order_address.get("lng"),
    }

    return {
        "external_reference": str(delivery.id),
        "partner": partner.slug,
        "fulfillment_mode": fulfillment_mode.value,
        "pickup": pickup,
        "dropoff": recipient,
        "distance_km": round(float(distance_km or 0), 2),
        "weight_kg": round(float(weight_kg or 0), 2),
        "declared_value": delivery.order.total,
        "currency": partner.currency or "KES",
        "instructions": delivery.order.notes,
        # Parcels are optional; most partners accept an order-level handover.
        "parcels": [
            {
                "name": (item.product_snapshot or {}).get("name"),
                "quantity": item.quantity,
                "sku": (item.product_snapshot or {}).get("sku"),
            }
            for item in (delivery.order.items or [])
        ],
    }


# ── Outbound dispatch ──────────────────────────────────────────────────────────


def _auth_headers(partner: PartnerFleet, api_key: str) -> dict:
    name = partner.auth_header_name or "Authorization"
    prefix = partner.auth_header_prefix
    return {name: f"{prefix} {api_key}".strip() if prefix else api_key}


def dispatch_job(
    db: Session,
    partner: PartnerFleet,
    job: PartnerJob,
    *,
    dispatch_path: str = "/v1/jobs",
) -> PartnerJob:
    """POST the job to the partner. Marks the job dispatched or failed.

    Does not raise on partner failure -- the failure is recorded on the job so
    ops can retry manually or fall back to an Ekshop rider.
    """
    if partner.status != PartnerStatus.active:
        raise PartnerNotConfigured(
            f"Partner {partner.slug} is '{partner.status.value}'; only active partners can take jobs"
        )

    api_key, _ = _require_credentials(partner)

    payload = {
        "external_reference": job.external_reference,
        "pickup": job.pickup_address,
        "dropoff": job.drop_address,
        "distance_km": job.distance_km,
        "weight_kg": float(job.weight_kg or 0),
    }

    url = f"{partner.api_base_url.rstrip('/')}/{dispatch_path.lstrip('/')}"
    now = datetime.now(timezone.utc)

    try:
        response = httpx.post(
            url,
            json=payload,
            headers={**_auth_headers(partner, api_key), "Content-Type": "application/json"},
            timeout=partner.timeout_seconds or 15,
        )
    except Exception as exc:
        job.status = PartnerJobStatus.failed
        job.failure_reason = f"Could not reach partner: {exc}"
        job.failed_at = now
        db.add(job)
        db.commit()
        logger.warning("Partner dispatch to %s failed at the network layer: %s", partner.slug, exc)
        return job

    body: Any
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text[:2000]}

    job.partner_raw_response = body

    if response.status_code >= 400:
        job.status = PartnerJobStatus.failed
        job.failure_reason = f"Partner returned {response.status_code}"
        job.failed_at = now
    else:
        job.status = PartnerJobStatus.dispatched
        job.dispatched_at = now
        if isinstance(body, dict):
            job.partner_job_id = (
                body.get("job_id")
                or body.get("id")
                or body.get("reference")
                or job.partner_job_id
            )
            fee = body.get("fee") or body.get("total") or body.get("amount")
            if fee is not None:
                try:
                    job.partner_reported_fee = str(Decimal(str(fee)))
                except Exception:
                    logger.debug("Partner %s returned a non-numeric fee %r", partner.slug, fee)

    partner.total_jobs += 1
    if job.status == PartnerJobStatus.failed:
        partner.failed_jobs += 1
    db.add_all([job, partner])
    db.commit()
    db.refresh(job)
    return job


def cancel_job(
    db: Session,
    partner: PartnerFleet,
    job: PartnerJob,
    *,
    cancel_path: str = "/v1/jobs/{external_reference}/cancel",
) -> PartnerJob:
    """Best-effort cancellation. Records intent even if the partner 404s."""
    if job.status in (PartnerJobStatus.delivered, PartnerJobStatus.cancelled):
        return job

    try:
        api_key, _ = _require_credentials(partner)
        url = partner.api_base_url.rstrip("/") + "/" + cancel_path.lstrip("/")
        url = url.replace("{external_reference}", str(job.external_reference or job.id))
        response = httpx.post(
            url,
            json={"reason": "cancelled_by_ekshop"},
            headers={**_auth_headers(partner, api_key), "Content-Type": "application/json"},
            timeout=partner.timeout_seconds or 15,
        )
        ok = response.status_code < 400
        detail = None if ok else f"Partner returned {response.status_code} on cancel"
    except Exception as exc:
        ok, detail = False, f"Cancel request failed: {exc}"

    job.status = PartnerJobStatus.cancelled
    job.failure_reason = job.failure_reason or detail
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# ── Inbound webhooks ───────────────────────────────────────────────────────────


def verify_signature(
    secret: str,
    body: bytes,
    signature: str | None,
    *,
    algorithm: str = "sha256",
) -> bool:
    """Constant-time HMAC comparison over the raw request body."""
    if not signature:
        return False
    digest = hmac.new(
        secret.encode(), body, getattr(hashlib, algorithm, hashlib.sha256)
    ).hexdigest()
    # Tolerate "sha256=<hex>" prefixes that several partners prepend.
    candidate = signature.split("=", 1)[1] if "=" in signature else signature
    return hmac.compare_digest(digest, candidate.strip())


def apply_partner_event(
    db: Session,
    partner: PartnerFleet,
    payload: dict,
    *,
    signature_valid: bool,
    partner_event_id: str | None = None,
) -> tuple[PartnerWebhookEvent, bool]:
    """Record a partner callback and mirror it onto the local Delivery.

    Returns (event, applied). Deduplicates on partner_event_id so partner
    retries are recorded but not re-applied.
    """
    event = PartnerWebhookEvent(
        partner_id=partner.id,
        partner_job_id=str(payload.get("job_id") or payload.get("id") or "") or None,
        event_type=str(payload.get("event") or payload.get("status") or "unknown"),
        payload=payload,
        signature_valid=signature_valid,
        partner_event_id=partner_event_id,
    )
    db.add(event)

    if not signature_valid:
        event.processing_error = "Rejected: invalid signature"
        db.commit()
        return event, False

    if partner_event_id:
        duplicate = (
            db.query(PartnerWebhookEvent.id)
            .filter(
                PartnerWebhookEvent.partner_id == partner.id,
                PartnerWebhookEvent.partner_event_id == partner_event_id,
                PartnerWebhookEvent.processed_at.isnot(None),
            )
            .first()
        )
        if duplicate:
            event.processing_error = "Ignored: duplicate of an already-processed event"
            db.commit()
            return event, False

    job_ref = payload.get("external_reference") or payload.get("job_id") or payload.get("id")
    job = (
        db.query(PartnerJob)
        .filter(
            PartnerJob.partner_id == partner.id,
            (PartnerJob.external_reference == str(job_ref))
            | (PartnerJob.partner_job_id == str(job_ref)),
        )
        .first()
    )
    if not job:
        event.processing_error = f"No local job matches reference {job_ref!r}"
        db.commit()
        return event, False

    try:
        _apply_partner_status(db, partner, job, payload)
    except Exception as exc:  # keep the audit row even if reconciliation blew up
        event.processing_error = f"Reconciliation failed: {exc}"
        db.commit()
        logger.exception("Partner %s event reconciliation failed", partner.slug)
        return event, False

    event.processed_at = datetime.now(timezone.utc)
    db.add(event)
    db.commit()
    return event, True


# Partner event vocabulary -> our PartnerJobStatus
_PARTNER_STATUS_MAP = {
    "created": PartnerJobStatus.created,
    "queued": PartnerJobStatus.created,
    "dispatched": PartnerJobStatus.dispatched,
    "assigned": PartnerJobStatus.accepted,
    "accepted": PartnerJobStatus.accepted,
    "driver_assigned": PartnerJobStatus.accepted,
    "collected": PartnerJobStatus.picked_up,
    "picked_up": PartnerJobStatus.picked_up,
    "pickup_completed": PartnerJobStatus.picked_up,
    "in_transit": PartnerJobStatus.in_transit,
    "out_for_delivery": PartnerJobStatus.in_transit,
    "delivered": PartnerJobStatus.delivered,
    "completed": PartnerJobStatus.delivered,
    "failed": PartnerJobStatus.failed,
    "cancelled": PartnerJobStatus.cancelled,
    "canceled": PartnerJobStatus.cancelled,
    "returned": PartnerJobStatus.returned,
}

# PartnerJobStatus -> our DeliveryStatus, for the subset we can mirror.
_DELIVERY_STATUS_MAP = {
    PartnerJobStatus.accepted: DeliveryStatus.assigned,
    PartnerJobStatus.picked_up: DeliveryStatus.picked,
    PartnerJobStatus.in_transit: DeliveryStatus.in_transit,
    PartnerJobStatus.delivered: DeliveryStatus.delivered,
    PartnerJobStatus.cancelled: DeliveryStatus.cancelled,
}

_TS_FIELDS = {
    "accepted": "accepted_at",
    "picked_up": "picked_up_at",
    "in_transit": "in_transit_at",
    "delivered": "delivered_at",
    "failed": "failed_at",
}


def _coerce_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _apply_partner_status(
    db: Session,
    partner: PartnerFleet,
    job: PartnerJob,
    payload: dict,
) -> None:
    raw_status = str(payload.get("event") or payload.get("status") or "").lower()
    new_status = _PARTNER_STATUS_MAP.get(raw_status)
    now = datetime.now(timezone.utc)

    # Driver details are useful on every event, not just acceptance.
    driver = payload.get("driver") or {}
    if isinstance(driver, dict):
        job.driver_name = driver.get("name") or driver.get("driver_name") or job.driver_name
        job.driver_phone = driver.get("phone") or driver.get("driver_phone") or job.driver_phone
        job.vehicle_plate = (
            driver.get("plate")
            or driver.get("vehicle_plate")
            or driver.get("registration")
            or job.vehicle_plate
        )

    if new_status is None:
        # Unknown vocabulary: keep the job, just archive the payload.
        job.partner_raw_response = payload
        db.add(job)
        db.commit()
        return

    ts_field = _TS_FIELDS.get(new_status.value)
    if ts_field:
        stamp = _coerce_timestamp(payload.get("timestamp") or payload.get("occurred_at")) or now
        setattr(job, ts_field, stamp)

    job.partner_job_id = str(payload.get("job_id") or payload.get("id") or job.partner_job_id or "") or None
    job.partner_raw_response = payload

    if new_status == PartnerJobStatus.failed:
        job.failure_reason = (
            payload.get("reason") or payload.get("failure_reason") or "Partner reported failure"
        )

    previous = job.status
    job.status = new_status

    delivery = job.delivery
    if delivery is not None:
        target = _DELIVERY_STATUS_MAP.get(new_status)
        # Never walk our own Delivery backwards.
        if target is not None and delivery.status != DeliveryStatus.delivered:
            delivery.status = target
            db.add(delivery)

    if new_status == PartnerJobStatus.failed and previous != PartnerJobStatus.failed:
        partner.failed_jobs += 1
        if partner.total_jobs:
            partner.success_rate = round(
                (partner.total_jobs - partner.failed_jobs) / partner.total_jobs, 4
            )

    db.add_all([job, partner])
    db.commit()


# ── Reporting ──────────────────────────────────────────────────────────────────


def partner_performance(db: Session, partner_id: uuid.UUID) -> dict:
    """Ops-facing reliability snapshot for one partner."""
    partner = db.get(PartnerFleet, partner_id)
    if not partner:
        raise PartnerNotConfigured(f"No partner fleet with id {partner_id}")

    jobs = db.query(PartnerJob).filter(PartnerJob.partner_id == partner_id).all()
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.status.value] = counts.get(job.status.value, 0) + 1

    delivered = [j for j in jobs if j.status == PartnerJobStatus.delivered]
    pick_deltas = [
        (j.picked_up_at - j.dispatched_at).total_seconds() / 60.0
        for j in jobs
        if j.picked_up_at and j.dispatched_at
    ]
    drop_deltas = [
        (j.delivered_at - j.picked_up_at).total_seconds() / 60.0
        for j in jobs
        if j.delivered_at and j.picked_up_at
    ]

    def _avg(values: list[float]) -> Optional[float]:
        return round(sum(values) / len(values), 1) if values else None

    return {
        "partner_id": str(partner.id),
        "name": partner.name,
        "status": partner.status.value,
        "total_jobs": len(jobs),
        "status_breakdown": counts,
        "success_rate": round(len(delivered) / len(jobs), 4) if jobs else None,
        "avg_pickup_minutes": _avg(pick_deltas),
        "avg_delivery_minutes": _avg(drop_deltas),
        "total_quoted_cost": str(sum((Decimal(j.quoted_fee or 0) for j in jobs), Decimal("0"))),
        "total_partner_reported_cost": str(
            sum((Decimal(j.partner_reported_fee or 0) for j in jobs), Decimal("0"))
        ),
    }