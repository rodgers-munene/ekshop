"""Partner fleet (3PL) router: admin management, dispatch, and webhooks."""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, selectinload

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models.commerce import Order
from app.models.delivery import (
    Delivery,
    PartnerFleet,
    PartnerJob,
    PartnerJobStatus,
    PartnerStatus,
    PartnerWebhookEvent,
)
from app.models.shop import Shop
from app.schemas.partner_fleet import (
    PartnerFleetCreate,
    PartnerFleetRead,
    PartnerFleetUpdate,
    PartnerJobCancelRead,
    PartnerJobCreate,
    PartnerJobListResponse,
    PartnerJobRead,
    PartnerPerformanceRead,
    PartnerQuoteRead,
    PartnerWebhookRead,
    PartnerWebhookResultRead,
)
from app.services import partner_fleet as pf

router = APIRouter(prefix="/delivery/partners", tags=["delivery-partners"])

logger = logging.getLogger(__name__)


def _fleet_read(partner: PartnerFleet) -> PartnerFleetRead:
    """Serialise a partner, swapping credential ciphertext for presence flags."""
    payload = PartnerFleetRead.model_validate(partner)
    return payload.model_copy(
        update={
            "has_api_key": bool(partner.api_key_encrypted),
            "has_webhook_secret": bool(partner.webhook_secret_encrypted),
            "base_pickup_fee": str(partner.base_pickup_fee or "0"),
            "per_km_fee": str(partner.per_km_fee or "0"),
            "per_kg_fee": str(partner.per_kg_fee or "0"),
        }
    )


def _get_partner_or_404(partner_id: uuid.UUID, db: Session) -> PartnerFleet:
    partner = db.get(PartnerFleet, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner fleet not found")
    return partner


# ── Partner fleet CRUD ─────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=PartnerFleetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a partner courier/3PL",
)
def create_partner_fleet(
    payload: PartnerFleetCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    if db.query(PartnerFleet).filter(PartnerFleet.slug == payload.slug).first():
        raise HTTPException(status_code=409, detail=f"Partner slug '{payload.slug}' already exists")

    partner = PartnerFleet(
        name=payload.name,
        slug=payload.slug,
        api_base_url=payload.api_base_url,
        auth_header_name=payload.auth_header_name,
        auth_header_prefix=payload.auth_header_prefix,
        supports_webhooks=payload.supports_webhooks,
        timeout_seconds=payload.timeout_seconds,
        base_pickup_fee=payload.base_pickup_fee,
        per_km_fee=payload.per_km_fee,
        per_kg_fee=payload.per_kg_fee,
        currency=payload.currency,
        coverage_counties=payload.coverage_counties,
        notes=payload.notes,
    )
    if payload.api_key:
        pf.set_partner_api_key(partner, payload.api_key)
    if payload.webhook_secret:
        pf.set_partner_webhook_secret(partner, payload.webhook_secret)

    db.add(partner)
    db.commit()
    db.refresh(partner)
    return _fleet_read(partner)


@router.get("", response_model=list[PartnerFleetRead], summary="List partner fleets")
def list_partner_fleets(
    status_filter: Optional[PartnerStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    query = db.query(PartnerFleet)
    if status_filter:
        query = query.filter(PartnerFleet.status == status_filter)
    return [_fleet_read(p) for p in query.order_by(PartnerFleet.name).all()]


@router.get("/{partner_id}", response_model=PartnerFleetRead, summary="Get a partner fleet")
def get_partner_fleet(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    return _fleet_read(_get_partner_or_404(partner_id, db))


@router.patch(
    "/{partner_id}",
    response_model=PartnerFleetRead,
    summary="Update a partner fleet (including rotating credentials)",
)
def update_partner_fleet(
    partner_id: uuid.UUID,
    payload: PartnerFleetUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    partner = _get_partner_or_404(partner_id, db)

    data = payload.model_dump(exclude_unset=True)
    for field in ("api_key", "webhook_secret"):
        data.pop(field, None)
    for field, value in data.items():
        setattr(partner, field, value)

    # Credentials are write-only; only re-encrypt when actually supplied.
    if payload.api_key:
        pf.set_partner_api_key(partner, payload.api_key)
    if payload.webhook_secret:
        pf.set_partner_webhook_secret(partner, payload.webhook_secret)

    db.add(partner)
    db.commit()
    db.refresh(partner)
    return _fleet_read(partner)


@router.post(
    "/{partner_id}/activate",
    response_model=PartnerFleetRead,
    summary="Activate a partner fleet once credentials are configured",
)
def activate_partner_fleet(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    """Credentials must exist before a partner is allowed to take live jobs."""
    partner = _get_partner_or_404(partner_id, db)
    missing = [
        name
        for name, value in (
            ("api_base_url", partner.api_base_url),
            ("api_key", partner.api_key_encrypted),
        )
        if not value
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot activate: missing {', '.join(missing)}",
        )
    partner.status = PartnerStatus.active
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return _fleet_read(partner)


@router.delete(
    "/{partner_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a partner fleet",
)
def delete_partner_fleet(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    partner = _get_partner_or_404(partner_id, db)
    db.delete(partner)
    db.commit()


# ── Quoting and dispatch ───────────────────────────────────────────────────────


def _delivery_context(delivery: Delivery, db: Session) -> tuple[Shop | None, dict]:
    """Load the order/shop and normalise the two addresses for a job payload."""
    delivery = (
        db.query(Delivery)
        .options(
            selectinload(Delivery.order).selectinload(Order.shop),
            selectinload(Delivery.order).selectinload(Order.items),
        )
        .filter(Delivery.id == delivery.id)
        .first()
    )
    if delivery is None or delivery.order is None:
        raise HTTPException(status_code=404, detail="Delivery or order not found")
    return delivery.order.shop, delivery.order.delivery_address or {}


@router.get(
    "/{partner_id}/quote",
    response_model=PartnerQuoteRead,
    summary="Quote what a partner would charge for a leg",
)
def quote_partner_leg(
    partner_id: uuid.UUID,
    distance_km: float = Query(..., ge=0),
    weight_kg: float = Query(0.0, ge=0),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    partner = _get_partner_or_404(partner_id, db)
    fee = pf.quote_partner_job(partner, distance_km=distance_km, weight_kg=weight_kg)
    ttl = pf.estimate_partner_ttl(partner, distance_km)
    return PartnerQuoteRead(
        partner_id=partner.id,
        partner_name=partner.name,
        distance_km=distance_km,
        weight_kg=weight_kg,
        quoted_fee=str(fee),
        currency=partner.currency or "KES",
        estimated_ttl_minutes=round(ttl.total_seconds() / 60.0, 1),
    )


@router.post(
    "/jobs",
    response_model=PartnerJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Hand a delivery to a partner fleet",
)
def create_partner_job(
    payload: PartnerJobCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    partner = _get_partner_or_404(payload.partner_id, db)
    if partner.status != PartnerStatus.active:
        raise HTTPException(
            status_code=409,
            detail=f"Partner {partner.slug} is '{partner.status.value}', not active",
        )

    delivery = db.get(Delivery, payload.delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    existing = (
        db.query(PartnerJob)
        .filter(
            PartnerJob.delivery_id == delivery.id,
            PartnerJob.partner_id == partner.id,
            PartnerJob.status.notin_(
                [PartnerJobStatus.failed, PartnerJobStatus.cancelled, PartnerJobStatus.delivered]
            ),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Delivery already has an in-flight partner job ({existing.id})",
        )

    shop, order_address = _delivery_context(delivery, db)
    body = pf.build_job_payload(
        partner,
        delivery,
        distance_km=payload.distance_km,
        weight_kg=payload.weight_kg,
        fulfillment_mode=payload.fulfillment_mode,
    )

    job = PartnerJob(
        partner_id=partner.id,
        delivery_id=delivery.id,
        external_reference=str(delivery.id),
        status=PartnerJobStatus.created,
        fulfillment_mode=payload.fulfillment_mode,
        pickup_address=body["pickup"],
        pickup_lat=(shop.lat if shop else None),
        pickup_lng=(shop.lng if shop else None),
        drop_address=body["dropoff"],
        drop_lat=order_address.get("lat"),
        drop_lng=order_address.get("lng"),
        distance_km=payload.distance_km,
        weight_kg=Decimal(str(payload.weight_kg)),
        quoted_fee=pf.quote_partner_job(
            partner, distance_km=payload.distance_km, weight_kg=payload.weight_kg
        ),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if payload.dispatch_immediately:
        # dispatch_job records failures on the job rather than raising.
        job = pf.dispatch_job(db, partner, job)
    return job


@router.post(
    "/jobs/{job_id}/dispatch",
    response_model=PartnerJobRead,
    summary="Retry dispatch for a staged or failed partner job",
)
def dispatch_existing_partner_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    job = db.get(PartnerJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Partner job not found")
    if job.status not in (PartnerJobStatus.created, PartnerJobStatus.failed):
        raise HTTPException(
            status_code=409,
            detail=f"Job is '{job.status.value}' and cannot be re-dispatched",
        )
    return pf.dispatch_job(db, job.partner, job)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=PartnerJobCancelRead,
    summary="Cancel a partner job",
)
def cancel_partner_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    job = db.get(PartnerJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Partner job not found")
    job = pf.cancel_job(db, job.partner, job)
    return PartnerJobCancelRead(
        job=PartnerJobRead.model_validate(job),
        cancelled_at_partner=job.failure_reason is None,
        detail=job.failure_reason,
    )


@router.get(
    "/jobs",
    response_model=PartnerJobListResponse,
    summary="List partner jobs",
)
def list_partner_jobs(
    partner_id: Optional[uuid.UUID] = Query(None),
    delivery_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[PartnerJobStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    query = db.query(PartnerJob)
    if partner_id:
        query = query.filter(PartnerJob.partner_id == partner_id)
    if delivery_id:
        query = query.filter(PartnerJob.delivery_id == delivery_id)
    if status_filter:
        query = query.filter(PartnerJob.status == status_filter)

    total = query.count()
    rows = (
        query.order_by(PartnerJob.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return PartnerJobListResponse(
        total=total,
        page=page,
        limit=limit,
        results=[PartnerJobRead.model_validate(row) for row in rows],
    )


@router.get(
    "/jobs/{job_id}",
    response_model=PartnerJobRead,
    summary="Get a partner job",
)
def get_partner_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    job = db.get(PartnerJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Partner job not found")
    return job


@router.get(
    "/{partner_id}/performance",
    response_model=PartnerPerformanceRead,
    summary="Partner reliability/cost snapshot",
)
def get_partner_performance(
    partner_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    return pf.partner_performance(db, partner_id)


@router.get(
    "/webhooks/events",
    response_model=list[PartnerWebhookRead],
    summary="Inspect inbound partner callbacks",
)
def list_partner_webhook_events(
    partner_id: Optional[uuid.UUID] = Query(None),
    signature_valid: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    query = db.query(PartnerWebhookEvent)
    if partner_id:
        query = query.filter(PartnerWebhookEvent.partner_id == partner_id)
    if signature_valid is not None:
        query = query.filter(PartnerWebhookEvent.signature_valid == signature_valid)
    return (
        query.order_by(PartnerWebhookEvent.created_at.desc()).limit(limit).all()
    )


# ── Inbound webhook (public, signature-verified) ───────────────────────────────


@router.post(
    "/{partner_id}/webhook",
    response_model=PartnerWebhookResultRead,
    summary="Inbound status callback from a partner courier",
    description="""
Partners post delivery status updates here. The request body is verified with
HMAC-SHA256 against the partner's stored webhook secret before it is applied to
the local Delivery. Unauthenticated callers get a 200 ack with
`signature_valid=false` so partners do not hot-loop on retries, and the raw event
is still logged for audit.
""",
)
async def receive_partner_webhook(
    partner_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    partner = db.get(PartnerFleet, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner fleet not found")

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Body is not valid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    signature = (
        request.headers.get("X-Signature")
        or request.headers.get("X-Webhook-Signature")
        or request.headers.get("X-Ekshop-Signature")
    )

    signature_valid = False
    if partner.webhook_secret_encrypted:
        try:
            secret = pf.decrypt_api_key(partner.webhook_secret_encrypted)
            signature_valid = pf.verify_signature(secret, raw_body, signature)
        except ValueError:
            logger.warning(
                "Partner %s webhook secret undecryptable; rejecting callback",
                partner.slug,
            )
    else:
        logger.warning(
            "Partner %s has no webhook secret configured; rejecting callback",
            partner.slug,
        )

    event_id = (
        payload.get("event_id")
        or payload.get("id")
        or (request.headers.get("X-Event-Id") if raw_body else None)
    )

    event, applied = pf.apply_partner_event(
        db,
        partner,
        payload,
        signature_valid=signature_valid,
        partner_event_id=str(event_id) if event_id else None,
    )

    return PartnerWebhookResultRead(
        # Always ack 200 so partners stop retrying a body we did record.
        accepted=True,
        signature_valid=signature_valid,
        applied=applied,
        detail=event.processing_error,
        event_id=str(event.id),
    )