"""Fulfillment state machine.

Two invariants are enforced here, both from the PRD:

1. **Validated transitions.** A job cannot skip states (created -> delivered is
   rejected), and cannot move backwards. A job that is delivered or cancelled
   is terminal unless a *new* job is created for a retry or return.

2. **History is never mutated.** Every transition appends a
   ``DeliveryJobEvent``. Retries and returns create a new ``DeliveryJob`` with
   an incremented ``attempt``; nothing is ever overwritten. That is what makes
   SLA reporting, rider performance, and dispute resolution possible later.

Callers must go through :func:`transition_job` rather than assigning
``job.status`` directly.

Transaction control
-------------------
The functions that change a *fulfillment* (``create_fulfillment``,
``open_retry_job``, ``open_return_job``, ``record_job_settlement``,
``settle_fulfillment``) commit before returning, so they are safe to call from a
request handler on their own. The lower-level job and assignment functions
(:func:`transition_job`, :func:`create_assignment`, :func:`respond_to_assignment`,
:func:`issue_otp`, :func:`override_job`) only ``flush()``: they leave the
transaction open so several steps can be recorded as one unit. A router that
calls those directly is responsible for ``db.commit()``.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from app.models.fulfillment import (
    AssignmentStatus,
    DeliveryAssignment,
    DeliveryJob,
    DeliveryJobEvent,
    DeliveryJobStatus,
    DeliveryJobType,
    Fulfillment,
    FulfillmentMode,
    FulfillmentSettlement,
    JobSettlement,
)

logger = logging.getLogger(__name__)


class FulfillmentError(RuntimeError):
    """A request that is well-formed but not allowed in the current state.

    The base class for every error this module raises on purpose. Callers should
    catch this one; the HTTP layer maps it to 400, or to 409 for
    :class:`InvalidTransition`.
    """


class InvalidTransition(FulfillmentError):
    """A transition that the state machine does not permit.

    Deliberately a subclass of :class:`FulfillmentError` and not a sibling of it:
    a rejected transition is still a fulfillment error, so a caller that catches
    the base class must not let it escape as an unhandled 500.
    """


# Legal forward transitions. Absence of a key means the state is terminal.
ALLOWED_TRANSITIONS: dict[DeliveryJobStatus, set[DeliveryJobStatus]] = {
    DeliveryJobStatus.created: {
        DeliveryJobStatus.dispatch_requested,
        DeliveryJobStatus.cancelled,
        DeliveryJobStatus.picked_up,  # mode=pickup: customer collects directly
    },
    DeliveryJobStatus.dispatch_requested: {
        DeliveryJobStatus.offered,
        DeliveryJobStatus.accepted,  # manual assign by ops
        DeliveryJobStatus.failed,
        DeliveryJobStatus.cancelled,
    },
    DeliveryJobStatus.offered: {
        DeliveryJobStatus.accepted,
        DeliveryJobStatus.dispatch_requested,  # wave exhausted -> restart
        DeliveryJobStatus.failed,
        DeliveryJobStatus.cancelled,
    },
    DeliveryJobStatus.accepted: {
        DeliveryJobStatus.at_pickup,
        DeliveryJobStatus.picked_up,  # self-delivery skips the rider trip
        DeliveryJobStatus.failed,
        DeliveryJobStatus.cancelled,
    },
    DeliveryJobStatus.at_pickup: {
        DeliveryJobStatus.picked_up,
        DeliveryJobStatus.failed,
        DeliveryJobStatus.cancelled,
    },
    DeliveryJobStatus.picked_up: {
        DeliveryJobStatus.in_transit,
        DeliveryJobStatus.delivered,
        DeliveryJobStatus.failed,
        DeliveryJobStatus.cancelled,
    },
    DeliveryJobStatus.in_transit: {DeliveryJobStatus.delivered, DeliveryJobStatus.failed},
    DeliveryJobStatus.delivered: {DeliveryJobStatus.settled},
    DeliveryJobStatus.failed: {DeliveryJobStatus.settled},  # to record the cost
    DeliveryJobStatus.settled: set(),
    DeliveryJobStatus.cancelled: set(),
    DeliveryJobStatus.returned: set(),
}

TERMINAL_STATUSES = {
    DeliveryJobStatus.settled,
    DeliveryJobStatus.cancelled,
    DeliveryJobStatus.returned,
}

# Which timestamp column each transition stamps.
_TIMESTAMP_FOR = {
    DeliveryJobStatus.dispatch_requested: "dispatch_requested_at",
    DeliveryJobStatus.offered: "dispatch_requested_at",
    DeliveryJobStatus.accepted: "accepted_at",
    DeliveryJobStatus.at_pickup: "at_pickup_at",
    DeliveryJobStatus.picked_up: "picked_up_at",
    DeliveryJobStatus.in_transit: "in_transit_at",
    DeliveryJobStatus.delivered: "delivered_at",
    DeliveryJobStatus.settled: "settled_at",
    DeliveryJobStatus.failed: "failed_at",
    DeliveryJobStatus.cancelled: "closed_at",
    DeliveryJobStatus.returned: "closed_at",
}

# Events that mean the job is finished but a follow-up job may be needed.
CLOSING_STATUSES = {DeliveryJobStatus.failed, DeliveryJobStatus.cancelled, DeliveryJobStatus.returned}


# ── OTP ────────────────────────────────────────────────────────────────────────


def generate_otp() -> str:
    """Six-digit code shown to the customer, stored only as a hash."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    """Peppered-free SHA-256 of the code.

    A 6-digit code has only a million possible values, so it is not safe to
    store a bare hash. The HMAC key below is the delivery job's
    ``external_reference``, which is unknown to an attacker holding a dump of
    this column, so a stolen table cannot be brute-forced offline at
    10^6 attempts per row. Rotate with rotation of the database dump, and
    treat a dump of delivery_jobs as sensitive.
    """
    key = _otp_pepper()
    return hmac.new(key.encode(), otp.encode(), hashlib.sha256).hexdigest()


def _otp_pepper() -> str:
    from app.core.config import settings

    pepper = getattr(settings, "DELIVERY_OTP_PEPPER", None)
    if not pepper:
        # Fail closed rather than hash with a constant key: a fixed pepper
        # would make every stored code brute-forceable from a table dump.
        raise FulfillmentError(
            "DELIVERY_OTP_PEPPER is not set. Generate one with "
            'python -c "import secrets; print(secrets.token_urlsafe(32))" and '
            "set it in the environment. Refusing to store OTPs without it."
        )
    return pepper


def verify_otp(job: DeliveryJob, otp: str) -> bool:
    """Check a delivery code, refusing anything expired.

    Expiry is enforced *here* rather than left to the caller. `transition_job`
    does check it separately, but a second caller that forgets would otherwise
    accept a code 31 minutes after it was minted -- and the whole point of the
    code is that it is only valid while the rider is standing at the door.
    `is_otp_expired` stays available for callers that want to check early and
    report a different message.
    """
    if not job.otp_hash or not otp:
        return False
    if is_otp_expired(job):
        return False
    return hmac.compare_digest(job.otp_hash, hash_otp(otp))


def is_otp_expired(job: DeliveryJob) -> bool:
    return bool(job.otp_expires_at) and job.otp_expires_at < datetime.now(timezone.utc)


# ── Events ─────────────────────────────────────────────────────────────────────


def record_event(
    db: Session,
    job: DeliveryJob,
    event_type: str,
    *,
    to_status: Optional[DeliveryJobStatus] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    actor_agent_id: Optional[uuid.UUID] = None,
    actor_role: Optional[str] = None,
    payload: Optional[dict] = None,
    notes: Optional[str] = None,
) -> DeliveryJobEvent:
    """Append to the job's log. Never updates or deletes existing rows.

    The event is appended to `job.events` as well as added to the session, so a
    caller that reads the log back before committing sees the new entry instead
    of a stale, already-loaded collection. Transaction control stays with the
    caller: nothing here commits.
    """
    event = DeliveryJobEvent(
        job_id=job.id,
        event_type=event_type,
        to_status=to_status,
        actor_user_id=actor_user_id,
        actor_agent_id=actor_agent_id,
        actor_role=actor_role,
        payload=payload,
        notes=notes,
    )
    job.events.append(event)
    db.add(event)
    return event


# ── Transitions ────────────────────────────────────────────────────────────────


def assert_transition_allowed(current: DeliveryJobStatus, target: DeliveryJobStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        if current in TERMINAL_STATUSES:
            raise InvalidTransition(
                f"'{current.value}' is terminal; create a new delivery job for a "
                f"retry or return instead of moving it to '{target.value}'"
            )
        options = ", ".join(sorted(s.value for s in allowed)) or "nothing"
        raise InvalidTransition(
            f"Cannot move a job from '{current.value}' to '{target.value}'. "
            f"Allowed: {options}"
        )


def transition_job(
    db: Session,
    job: DeliveryJob,
    target: DeliveryJobStatus,
    *,
    event_type: Optional[str] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    actor_agent_id: Optional[uuid.UUID] = None,
    actor_role: Optional[str] = None,
    payload: Optional[dict] = None,
    notes: Optional[str] = None,
    validate_otp: bool = False,
    otp: Optional[str] = None,
) -> DeliveryJob:
    """Move a job to `target`, appending an event and stamping the timestamp.

    `validate_otp=True` requires a valid, unexpired code before allowing the
    transition to `delivered` (PRD D2 / section 5.7).
    """
    current = job.status
    assert_transition_allowed(current, target)

    if target == DeliveryJobStatus.delivered and validate_otp:
        if not otp:
            raise FulfillmentError("A delivery code is required to mark this delivered")
        if is_otp_expired(job):
            raise FulfillmentError("The delivery code has expired")
        if not verify_otp(job, otp):
            raise FulfillmentError("Incorrect delivery code")

    now = datetime.now(timezone.utc)

    if target == DeliveryJobStatus.delivered and validate_otp:
        job.otp_verified_at = now

    job.status = target

    ts_field = _TIMESTAMP_FOR.get(target)
    if ts_field and getattr(job, ts_field) is None:
        setattr(job, ts_field, now)

    record_event(
        db,
        job,
        event_type or f"JOB_{target.value.upper()}",
        to_status=target,
        actor_user_id=actor_user_id,
        actor_agent_id=actor_agent_id,
        actor_role=actor_role,
        payload=payload,
        notes=notes,
    )
    db.add(job)
    return job


# ── Assignments (rider offers) ─────────────────────────────────────────────────


def create_assignment(
    db: Session,
    job: DeliveryJob,
    agent_id: uuid.UUID,
    *,
    wave: int = 1,
    payout_estimate: Optional[Decimal] = None,
    distance_km: Optional[Decimal] = None,
    ttl_seconds: int = 90,
) -> DeliveryAssignment:
    """Offer the job to a rider.

    The SLA matrix gives wave 1 a 60-90s window and wave 2 a 90s window, so
    the TTL is a parameter rather than a constant.
    """
    if job.status not in (
        DeliveryJobStatus.dispatch_requested,
        DeliveryJobStatus.offered,
    ):
        raise FulfillmentError(
            f"Cannot offer a job that is '{job.status.value}'; it must be in "
            f"dispatch_requested or offered"
        )

    existing = (
        db.query(DeliveryAssignment)
        .filter(
            DeliveryAssignment.job_id == job.id,
            DeliveryAssignment.agent_id == agent_id,
            DeliveryAssignment.wave == wave,
        )
        .first()
    )
    if existing:
        raise FulfillmentError(
            f"Rider {agent_id} has already been offered this job in wave {wave}"
        )

    now = datetime.now(timezone.utc)
    assignment = DeliveryAssignment(
        job_id=job.id,
        # Set explicitly so the relationship is populated without a lazy load:
        # the caller may respond to this offer before it is ever flushed.
        job=job,
        agent_id=agent_id,
        wave=wave,
        status=AssignmentStatus.offered,
        payout_estimate=payout_estimate,
        distance_km=distance_km,
        offered_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(assignment)
    # Flush (do not commit -- the caller owns the transaction) so the
    # assignment has an id for the event log and for the respond_to_assignment
    # payload.
    db.flush()
    record_event(
        db,
        job,
        "OFFER_SENT",
        actor_role="system",
        payload={
            "assignment_id": str(assignment.id),
            "agent_id": str(agent_id),
            "wave": wave,
            "expires_at": now.isoformat(),
        },
    )
    return assignment


def respond_to_assignment(
    db: Session,
    assignment: DeliveryAssignment,
    status: AssignmentStatus,
    *,
    decline_reason: Optional[str] = None,
) -> DeliveryAssignment:
    """Record a rider's accept/decline, or expire a stale offer.

    Accepting also claims the job for that rider (`job.agent_id`). Without this
    the rider would hold an accepted offer but still own no job, and every
    rider-facing lookup -- which authorises on `job.agent_id` -- would refuse
    them. Claiming here keeps the assignment and the ownership in one place
    instead of relying on each caller to remember.
    """
    if assignment.status in (AssignmentStatus.accepted, AssignmentStatus.cancelled):
        raise FulfillmentError(
            f"Assignment is already '{assignment.status.value}' and cannot be changed"
        )

    job = assignment.job
    if job is None:
        raise FulfillmentError("Assignment is not linked to a delivery job")
    if assignment.id is None:
        # An offer that was never flushed cannot be attributed in the event log.
        db.flush()

    assignment.status = status
    assignment.responded_at = datetime.now(timezone.utc)
    if decline_reason:
        assignment.decline_reason = decline_reason

    if status == AssignmentStatus.accepted:
        if job.agent_id is not None and job.agent_id != assignment.agent_id:
            raise FulfillmentError(
                "This job is already claimed by another rider; it cannot be "
                "accepted by a second rider"
            )
        job.agent_id = assignment.agent_id
        # Every other offer for this job is now moot.
        for other in job.assignments:
            if other.id != assignment.id and other.status == AssignmentStatus.offered:
                other.status = AssignmentStatus.cancelled
                other.responded_at = assignment.responded_at
                record_event(
                    db,
                    job,
                    "OFFER_WITHDRAWN",
                    actor_role="system",
                    payload={"agent_id": str(other.agent_id), "wave": other.wave},
                )
        db.add(job)

    record_event(
        db,
        job,
        "RIDER_ACCEPTED" if status == AssignmentStatus.accepted else "OFFER_DECLINED",
        actor_agent_id=assignment.agent_id,
        actor_role="agent",
        payload={"assignment_id": str(assignment.id), "wave": assignment.wave},
        notes=decline_reason,
    )
    db.add(assignment)
    return assignment


def expire_stale_assignments(db: Session, job: DeliveryJob) -> int:
    """Expire offers whose window has passed. Returns the number expired."""
    now = datetime.now(timezone.utc)
    stale = (
        db.query(DeliveryAssignment)
        .filter(
            DeliveryAssignment.job_id == job.id,
            DeliveryAssignment.status == AssignmentStatus.offered,
            DeliveryAssignment.expires_at < now,
        )
        .all()
    )
    for assignment in stale:
        respond_to_assignment(db, assignment, AssignmentStatus.expired)
    return len(stale)


# ── Fulfillment lifecycle ──────────────────────────────────────────────────────


def create_fulfillment(
    db: Session,
    order_id: uuid.UUID,
    *,
    mode: FulfillmentMode,
    merchant_subsidy: Decimal = Decimal("0"),
    ekshop_subsidy: Decimal = Decimal("0"),
    self_rider_name: Optional[str] = None,
    self_rider_phone: Optional[str] = None,
    quoted_fee: Optional[Decimal] = None,
) -> Fulfillment:
    """Open a fulfillment and its first job.

    mode=self requires a rider name and phone (PRD 5.3) -- a self-delivery
    with nobody named cannot produce a trackable timeline.

    Subsidies follow spec10 / Appendix B.1: the merchant and Ekshop may each
    contribute toward the delivery, and the customer pays the remainder. A
    subsidy changes *who pays*, never the total -- `delivery_price_gross` stays
    the full computed price and contribution is always computed on the gross,
    so a fully-subsidised delivery still shows the real cost of serving it.

    No OTP is issued here. A delivery code is only useful moments before the
    rider arrives, and the code expires in 30 minutes, so issuing one when the
    order is created would hand the customer an already-dead code. Call
    `issue_otp` when the job is dispatched. (`open_retry_job` does issue one,
    because a retry means a rider is being re-dispatched right now.)
    """
    if mode == FulfillmentMode.self_ and not (self_rider_name and self_rider_phone):
        raise FulfillmentError(
            "Self-delivery requires the merchant's rider name and phone"
        )
    merchant_subsidy = _decimal(merchant_subsidy, "merchant_subsidy")
    ekshop_subsidy = _decimal(ekshop_subsidy, "ekshop_subsidy")
    if merchant_subsidy < 0 or ekshop_subsidy < 0:
        raise FulfillmentError("A subsidy cannot be negative")

    existing = db.query(Fulfillment).filter(Fulfillment.order_id == order_id).first()
    if existing:
        raise FulfillmentError(
            f"Order already has a fulfillment ({existing.id}) in mode "
            f"'{existing.mode.value}'; close it before opening another"
        )

    now = datetime.now(timezone.utc)
    fulfillment = Fulfillment(
        order_id=order_id,
        mode=mode,
        merchant_subsidy=merchant_subsidy,
        ekshop_subsidy=ekshop_subsidy,
        self_rider_name=self_rider_name,
        self_rider_phone=self_rider_phone,
        quoted_fee=quoted_fee,
        quoted_at=now if quoted_fee is not None else None,
    )
    db.add(fulfillment)
    db.flush()  # need fulfillment.id for the job

    job = _new_job(db, fulfillment, job_type=DeliveryJobType.forward, attempt=1)
    record_event(
        db,
        job,
        "JOB_CREATED",
        actor_role="merchant",
        payload={
            "mode": mode.value,
            "merchant_subsidy": str(merchant_subsidy),
            "ekshop_subsidy": str(ekshop_subsidy),
        },
    )
    db.add(job)
    db.commit()
    db.refresh(fulfillment)
    return fulfillment


def _new_job(
    db: Session,
    fulfillment: Fulfillment,
    *,
    job_type: DeliveryJobType,
    attempt: int,
    reason: Optional[str] = None,
) -> DeliveryJob:
    """Create the next job under a fulfillment. The only way to make a new
    attempt -- existing jobs are never reopened or reused."""
    order = fulfillment.order
    if order is None:
        raise FulfillmentError("Fulfillment has no order loaded")

    address = order.delivery_address or {}
    shop = order.shop

    job = DeliveryJob(
        fulfillment_id=fulfillment.id,
        # Stable, unique, and safe to hand to a third party.
        external_reference=uuid.uuid4().hex,
        attempt=attempt,
        job_type=job_type,
        status=DeliveryJobStatus.created,
        pickup_lat=shop.lat if shop else None,
        pickup_lng=shop.lng if shop else None,
        drop_lat=address.get("lat"),
        drop_lng=address.get("lng"),
        quoted_fee=fulfillment.quoted_fee,
    )
    if job_type == DeliveryJobType.return_:
        # A return leg runs merchant -> customer, not the other way round.
        job.pickup_lat = job.drop_lat
        job.pickup_lng = job.drop_lng
        job.drop_lat = shop.lat if shop else None
        job.drop_lng = shop.lng if shop else None

    db.add(job)
    db.flush()

    if reason:
        record_event(
            db, job, "JOB_CREATED", actor_role="system", notes=reason
        )
    return job


def open_retry_job(
    db: Session,
    fulfillment: Fulfillment,
    *,
    actor_user_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
) -> DeliveryJob:
    """Create a new FORWARD job after a failed attempt.

    History is preserved: the failed job and its events stay exactly as they
    were. Only `attempt` increments and a fresh OTP is issued.
    """
    current = fulfillment.current_job
    if current is None:
        raise FulfillmentError("Fulfillment has no delivery job to retry")
    if current.status not in CLOSING_STATUSES | {DeliveryJobStatus.delivered}:
        raise FulfillmentError(
            f"Current job is '{current.status.value}'; only a failed, cancelled, "
            f"returned or delivered job can be retried"
        )
    if any(j.job_type == DeliveryJobType.forward and j.status not in CLOSING_STATUSES
           for j in fulfillment.jobs):
        raise FulfillmentError("An earlier attempt is still in flight")

    next_attempt = max(j.attempt for j in fulfillment.jobs) + 1
    job = _new_job(
        db,
        fulfillment,
        job_type=DeliveryJobType.forward,
        attempt=next_attempt,
        reason=reason or f"Retry after job {current.id} ended as {current.status.value}",
    )
    issue_otp(db, job, actor_user_id=actor_user_id)
    record_event(
        db,
        job,
        "RETRY_OPENED",
        actor_user_id=actor_user_id,
        actor_role="system",
        payload={"previous_job_id": str(current.id), "previous_status": current.status.value},
    )
    db.commit()
    db.refresh(job)
    return job


def open_return_job(
    db: Session,
    fulfillment: Fulfillment,
    *,
    actor_user_id: Optional[uuid.UUID] = None,
    reason: Optional[str] = None,
) -> DeliveryJob:
    """Create a RETURN leg carrying goods back to the merchant."""
    if any(j.job_type == DeliveryJobType.return_ for j in fulfillment.jobs):
        raise FulfillmentError("A return job already exists for this fulfillment")

    current = fulfillment.current_job
    next_attempt = max(j.attempt for j in fulfillment.jobs) + 1
    job = _new_job(
        db,
        fulfillment,
        job_type=DeliveryJobType.return_,
        attempt=next_attempt,
        reason=reason or "Return to merchant",
    )
    record_event(
        db,
        job,
        "RETURN_OPENED",
        actor_user_id=actor_user_id,
        actor_role="system",
        payload={"previous_job_id": str(current.id) if current else None, "reason": reason},
    )
    fulfillment.closed_at = datetime.now(timezone.utc)
    fulfillment.close_reason = reason or "Returned to merchant"
    db.commit()
    db.refresh(job)
    return job


def issue_otp(
    db: Session,
    job: DeliveryJob,
    *,
    actor_user_id: Optional[uuid.UUID] = None,
    ttl_minutes: int = 30,
) -> str:
    """Issue a fresh delivery code for a job. Returns the plaintext so the
    caller can show it to the customer; only the hash is persisted."""
    otp = generate_otp()
    job.otp_hash = hash_otp(otp)
    job.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    job.otp_verified_at = None
    record_event(
        db,
        job,
        "OTP_ISSUED",
        actor_user_id=actor_user_id,
        actor_role="system",
        payload={"expires_at": job.otp_expires_at.isoformat()},
    )
    db.add(job)
    return otp


def close_fulfillment(
    db: Session,
    fulfillment: Fulfillment,
    *,
    reason: str,
    actor_user_id: Optional[uuid.UUID] = None,
) -> Fulfillment:
    """Close a fulfillment. `status` stays derived; only the close marker moves."""
    if fulfillment.closed_at is not None:
        raise FulfillmentError(
            f"Fulfillment is already closed ({fulfillment.close_reason})"
        )
    fulfillment.closed_at = datetime.now(timezone.utc)
    fulfillment.close_reason = reason
    if fulfillment.confirmed_at is None:
        fulfillment.confirmed_at = fulfillment.created_at
    record_event(
        db,
        fulfillment.current_job,
        "FULFILLMENT_CLOSED",
        actor_user_id=actor_user_id,
        actor_role="ops",
        notes=reason,
    )
    db.add(fulfillment)
    db.commit()
    return fulfillment


def override_job(
    db: Session,
    job: DeliveryJob,
    *,
    reason: str,
    actor_user_id: Optional[uuid.UUID],
    target: DeliveryJobStatus = DeliveryJobStatus.cancelled,
    notes: Optional[str] = None,
) -> DeliveryJob:
    """Ops escape hatch (PRD G3). Always logged, never silent."""
    if not reason:
        raise FulfillmentError("An override requires a reason")
    job.overridden_at = datetime.now(timezone.utc)
    job.override_reason = reason
    record_event(
        db,
        job,
        "OPS_OVERRIDE",
        to_status=target,
        actor_user_id=actor_user_id,
        actor_role="ops",
        notes=reason,
    )
    return transition_job(
        db,
        job,
        target,
        event_type="OPS_OVERRIDE_APPLIED",
        actor_user_id=actor_user_id,
        actor_role="ops",
        notes=notes or reason,
    )


# ── Settlement ─────────────────────────────────────────────────────────────────


def _decimal(value, field: str) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FulfillmentError(f"{field} must be a valid decimal") from exc


def record_job_settlement(
    db: Session,
    job: DeliveryJob,
    *,
    fee_collected: Decimal = Decimal("0"),
    rider_payout: Decimal = Decimal("0"),
    incentive_paid: Decimal = Decimal("0"),
    payment_fee: Optional[Decimal] = None,
    partner_cost: Decimal = Decimal("0"),
    waiting_fee: Decimal = Decimal("0"),
    payment_fee_pct: Optional[Decimal] = None,
    actor_user_id: Optional[uuid.UUID] = None,
) -> JobSettlement:
    """Record the money for one attempt (PRD F1).

    Mirrors the margin calculator:
        contribution = fee_collected - rider_payout - incentive_paid
                       - payment_fee - partner_cost - waiting_fee

    Amounts are coerced through :func:`_decimal` so a string from a JSON body
    cannot blow up the arithmetic halfway through a settlement.

    Recording the money and closing the attempt are the same fact, so this also
    moves the job to `settled` and commits. A `failed` job can be settled too:
    a failed attempt still costs a rider payout and a payment fee, and the PRD
    wants that visible rather than lost.
    """
    if job.status not in (
        DeliveryJobStatus.delivered,
        DeliveryJobStatus.failed,
        DeliveryJobStatus.settled,
    ):
        raise FulfillmentError(
            f"Job is '{job.status.value}'; money can only be recorded against a "
            f"delivered or failed attempt"
        )
    if job.status == DeliveryJobStatus.settled and job.settlement is not None:
        raise FulfillmentError("This attempt has already been settled")

    fee_collected = _decimal(fee_collected, "fee_collected")
    rider_payout = _decimal(rider_payout, "rider_payout")
    incentive_paid = _decimal(incentive_paid, "incentive_paid")
    partner_cost = _decimal(partner_cost, "partner_cost")
    waiting_fee = _decimal(waiting_fee, "waiting_fee")

    if payment_fee is None:
        pct = _decimal(payment_fee_pct, "payment_fee_pct")
        payment_fee = (fee_collected * pct).quantize(Decimal("0.01"))
    else:
        payment_fee = _decimal(payment_fee, "payment_fee")

    contribution = (
        fee_collected
        - rider_payout
        - incentive_paid
        - payment_fee
        - partner_cost
        - waiting_fee
    ).quantize(Decimal("0.01"))

    settlement = JobSettlement(
        job_id=job.id,
        fee_collected=fee_collected,
        rider_payout=rider_payout,
        incentive_paid=incentive_paid,
        payment_fee=payment_fee,
        partner_cost=partner_cost,
        waiting_fee=waiting_fee,
        contribution=contribution,
    )
    db.add(settlement)
    record_event(
        db,
        job,
        "SETTLEMENT_RECORDED",
        actor_role="system",
        payload={
            "fee_collected": str(fee_collected),
            "rider_payout": str(rider_payout),
            "contribution": str(contribution),
        },
    )
    if job.status != DeliveryJobStatus.settled:
        transition_job(
            db,
            job,
            DeliveryJobStatus.settled,
            event_type="SETTLED",
            actor_user_id=actor_user_id,
            actor_role="system",
            payload={"contribution": str(contribution)},
        )
    db.commit()
    db.refresh(settlement)
    return settlement


def settle_fulfillment(
    db: Session,
    fulfillment: Fulfillment,
    *,
    actor_user_id: Optional[uuid.UUID] = None,
) -> FulfillmentSettlement:
    """Roll every job's settlement up onto the fulfillment (PRD F1).

    This is what makes the margin calculator's Zone Summary tab a plain SUM
    over `fulfillment_settlements` instead of a spreadsheet.
    """
    job = fulfillment.current_job
    if job is None:
        raise FulfillmentError("Fulfillment has no delivery job to settle")
    if job.status not in (DeliveryJobStatus.delivered, DeliveryJobStatus.settled):
        raise FulfillmentError(
            f"Job is '{job.status.value}'; only a delivered job can be settled"
        )

    # Every attempt that cost money must be settled first, otherwise the roll-up
    # would quietly under-report the margin. Cancelled attempts cost nothing.
    unsettled = [
        j
        for j in fulfillment.jobs
        if j.status != DeliveryJobStatus.cancelled and j.settlement is None
    ]
    if unsettled:
        raise FulfillmentError(
            f"{len(unsettled)} attempt(s) have no settlement recorded yet "
            f"(first: {unsettled[0].id} is '{unsettled[0].status.value}')"
        )

    parts = [j.settlement for j in fulfillment.jobs if j.settlement is not None]
    if not parts:
        raise FulfillmentError("No job settlement recorded yet")

    def total(attr: str) -> Decimal:
        return sum((_decimal(getattr(p, attr), attr) for p in parts), Decimal("0")).quantize(
            Decimal("0.01")
        )

    fee_collected = total("fee_collected")
    contribution = total("contribution")
    margin_pct = (
        (contribution / fee_collected).quantize(Decimal("0.0001"))
        if fee_collected > 0
        else Decimal("0")
    )

    settlement = FulfillmentSettlement(
        fulfillment_id=fulfillment.id,
        job_id=job.id,
        fee_collected=fee_collected,
        rider_payout=total("rider_payout"),
        incentive_paid=total("incentive_paid"),
        payment_fee=total("payment_fee"),
        partner_cost=total("partner_cost"),
        waiting_fee=total("waiting_fee"),
        contribution=contribution,
        margin_pct=margin_pct,
    )
    db.add(settlement)
    fulfillment.settled_at = datetime.now(timezone.utc)
    if fulfillment.closed_at is None:
        fulfillment.closed_at = fulfillment.settled_at
        fulfillment.close_reason = "settled"
    db.commit()
    db.refresh(settlement)
    return settlement
