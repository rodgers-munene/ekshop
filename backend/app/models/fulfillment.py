"""Fulfillment domain: the promise to get an order to the customer.

Per the fulfillment PRD, the hierarchy is:

    ORDER
      `-- FULFILLMENT          the promise; mode EKSHOP / SELF / PICKUP / PARTNER
            |-- DELIVERY JOB #1  one attempt to move the order (FORWARD)
            |     |-- ASSIGNMENTS  offers, accepts, reassignments
            |     `-- EVENTS       append-only; the truth about what happened
            |-- DELIVERY JOB #2  RETRY
            |-- DELIVERY JOB #3  RETURN to merchant
            `-- SETTLEMENT        payout / incentive / fees / contribution

Two rules drive the design:

1. One fulfillment may have many delivery jobs. A retry, a rider
   abandonment, or a return creates a *new* job rather than overwriting the
   previous one.
2. ``delivery_job_events`` is insert-only. ``status`` on the job is a
   convenience projection for queries; the event log is the record of truth.
   The insert-only rule is additionally enforced at the database level by
   revoking UPDATE/DELETE in the migration.

``fulfillments.status`` is deliberately NOT a stored enum column. It is
derived from the current job, so there is no way for the two to drift.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class FulfillmentMode(str, enum.Enum):
    """Who physically moves the goods."""

    ekshop = "ekshop"    # an Ekshop rider
    self_ = "self"      # the merchant's own rider ("I'll deliver myself")
    pickup = "pickup"    # customer collects from the merchant; no rider, no fee
    partner = "partner"  # external courier (3PL) via partner_fleets


class FulfillmentPayer(str, enum.Enum):
    """Who bears the delivery fee."""

    customer = "customer"
    merchant = "merchant"
    split = "split"


class FulfillmentStatus(str, enum.Enum):
    """Derived from the current job -- never written by hand."""

    pending = "pending"        # order confirmed, merchant has not chosen
    dispatching = "dispatching"  # offers going out
    in_progress = "in_progress"  # a rider is carrying it
    delivered = "delivered"
    failed = "failed"          # final attempt failed
    returned = "returned"      # returned to merchant
    cancelled = "cancelled"
    collected = "collected"    # customer picked up


class DeliveryJobType(str, enum.Enum):
    """Why this job exists."""

    forward = "forward"  # the initial attempt
    retry = "retry"      # a subsequent attempt after a failure
    return_ = "return"   # carrying goods back to the merchant


class DeliveryJobStatus(str, enum.Enum):
    """Mirrors the PRD state machine, minus the order-level stages."""

    created = "created"
    dispatch_requested = "dispatch_requested"
    offered = "offered"
    accepted = "accepted"
    at_pickup = "at_pickup"
    picked_up = "picked_up"
    in_transit = "in_transit"
    delivered = "delivered"      # OTP verified
    settled = "settled"
    failed = "failed"
    cancelled = "cancelled"
    returned = "returned"


class AssignmentStatus(str, enum.Enum):
    queued = "queued"
    offered = "offered"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    cancelled = "cancelled"


class Fulfillment(Base):
    """The promise to get an order to the customer. One per order in v1."""

    __tablename__ = "fulfillments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Unique in v1. The table exists so item-level grouping can be added later
    # without reshaping everything beneath it (PRD 7.3).
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)

    mode = Column(Enum(FulfillmentMode, native_enum=False), nullable=False)
    payer = Column(Enum(FulfillmentPayer, native_enum=False), default=FulfillmentPayer.customer, nullable=False)
    # For FulfillmentPayer.split: what fraction of the fee the customer bears.
    payer_split_pct = Column(Numeric(5, 2))

    # Merchant-supplied rider, for mode=self. Recorded on the fulfillment (not
    # the job) because it describes the merchant's capability, not one attempt.
    self_rider_name = Column(String(150))
    self_rider_phone = Column(String(20))

    # Pricing agreed at request time, so later schedule changes never rewrite
    # history for an order that was already quoted.
    quoted_fee = Column(Numeric(12, 2))
    quoted_at = Column(DateTime(timezone=True))
    confirmed_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    close_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_fulfillments_order_id", "order_id"),
        Index("ix_fulfillments_mode", "mode"),
    )

    order = relationship("Order", back_populates="fulfillments")
    jobs = relationship(
        "DeliveryJob",
        back_populates="fulfillment",
        cascade="all, delete-orphan",
        order_by="DeliveryJob.attempt",
    )
    settlement = relationship(
        "FulfillmentSettlement",
        back_populates="fulfillment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def current_job(self) -> "DeliveryJob | None":
        """The latest attempt, which is the one that represents current state."""
        return self.jobs[-1] if self.jobs else None

    @property
    def status(self) -> FulfillmentStatus:
        """Derived, never stored -- so it cannot drift from the job log."""
        job = self.current_job
        if self.close_reason and self.closed_at:
            pass  # fall through to job-derived status
        if job is None:
            return FulfillmentStatus.pending
        if self.mode == FulfillmentMode.pickup:
            return FulfillmentStatus.collected if job.status == DeliveryJobStatus.delivered else FulfillmentStatus.pending

        mapping = {
            DeliveryJobStatus.created: FulfillmentStatus.pending,
            DeliveryJobStatus.dispatch_requested: FulfillmentStatus.dispatching,
            DeliveryJobStatus.offered: FulfillmentStatus.dispatching,
            DeliveryJobStatus.accepted: FulfillmentStatus.in_progress,
            DeliveryJobStatus.at_pickup: FulfillmentStatus.in_progress,
            DeliveryJobStatus.picked_up: FulfillmentStatus.in_progress,
            DeliveryJobStatus.in_transit: FulfillmentStatus.in_progress,
            DeliveryJobStatus.delivered: FulfillmentStatus.delivered,
            DeliveryJobStatus.settled: FulfillmentStatus.delivered,
            DeliveryJobStatus.failed: FulfillmentStatus.failed,
            DeliveryJobStatus.returned: FulfillmentStatus.returned,
            DeliveryJobStatus.cancelled: FulfillmentStatus.cancelled,
        }
        return mapping.get(job.status, FulfillmentStatus.pending)


class DeliveryJob(Base):
    """One attempt to move an order to the customer.

    `status` is a projection for querying. `delivery_job_events` is the truth.
    """

    __tablename__ = "delivery_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fulfillment_id = Column(
        UUID(as_uuid=True), ForeignKey("fulfillments.id", ondelete="CASCADE"), nullable=False
    )
    # Our id, sent to third parties (rider offers, 3PL partners) as the
    # external reference. Stable across retries.
    external_reference = Column(String(64), unique=True, nullable=False)
    # 1 for the first attempt, 2 for the first retry, and so on. Makes the
    # "many jobs, ordered" relationship explicit and cheap to query.
    attempt = Column(Integer, nullable=False, default=1)

    job_type = Column(Enum(DeliveryJobType, native_enum=False), nullable=False, default=DeliveryJobType.forward)
    status = Column(
        Enum(DeliveryJobStatus, native_enum=False), nullable=False, default=DeliveryJobStatus.created
    )

    # Executor. Either an Ekshop rider, a partner fleet, or (for mode=self)
    # the merchant's own rider, in which case both are null.
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="SET NULL"))
    partner_job_id = Column(UUID(as_uuid=True), ForeignKey("partner_jobs.id", ondelete="SET NULL"))

    # Route, snapshotted at job creation so a later address edit cannot
    # rewrite what the rider actually agreed to carry.
    pickup_lat = Column(Numeric(9, 6))
    pickup_lng = Column(Numeric(9, 6))
    drop_lat = Column(Numeric(9, 6))
    drop_lng = Column(Numeric(9, 6))
    distance_km = Column(Numeric(10, 2))

    quoted_fee = Column(Numeric(12, 2))
    # Ops may override a job that is stuck; always logged, never silent.
    overridden_at = Column(DateTime(timezone=True))
    override_reason = Column(Text)

    # OTP is stored hashed (PRD D2). The plaintext is shown to the customer
    # and read back by the rider, so it must never sit in the database.
    otp_hash = Column(String(128))
    otp_expires_at = Column(DateTime(timezone=True))
    otp_verified_at = Column(DateTime(timezone=True))

    # Failure detail, per the SLA matrix's failure-state table.
    failure_code = Column(String(50))
    failure_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    dispatch_requested_at = Column(DateTime(timezone=True))
    accepted_at = Column(DateTime(timezone=True))
    at_pickup_at = Column(DateTime(timezone=True))
    pickup_confirmed_at = Column(DateTime(timezone=True))
    picked_up_at = Column(DateTime(timezone=True))
    in_transit_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    settled_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))

    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("fulfillment_id", "attempt", name="uq_delivery_job_attempt"),
        UniqueConstraint("fulfillment_id", "job_type", name="uq_delivery_job_type_per_fulfillment"),
        Index("ix_delivery_jobs_fulfillment_id", "fulfillment_id"),
        Index("ix_delivery_jobs_status", "status"),
        CheckConstraint("distance_km IS NULL OR distance_km >= 0", name="ck_delivery_job_distance"),
    )

    fulfillment = relationship("Fulfillment", back_populates="jobs")
    agent = relationship("DeliveryAgent")
    partner_job = relationship("PartnerJob")
    assignments = relationship(
        "DeliveryAssignment",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="DeliveryAssignment.created_at",
    )
    events = relationship(
        "DeliveryJobEvent",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="DeliveryJobEvent.created_at",
    )
    settlement = relationship(
        "JobSettlement", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )


class DeliveryAssignment(Base):
    """An offer to a rider, and what they did about it.

    Supersedes the narrower delivery_offers table. Reassignment inside one job
    is a new row here, so the sequence of offers is reconstructable.
    """

    __tablename__ = "delivery_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False)

    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    wave = Column(Integer, nullable=False, default=1)
    status = Column(
        Enum(AssignmentStatus, native_enum=False), nullable=False, default=AssignmentStatus.queued
    )

    payout_estimate = Column(Numeric(12, 2))
    distance_km = Column(Numeric(10, 2))

    offered_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    responded_at = Column(DateTime(timezone=True))
    # Why this offer did not land, for rider-performance reporting.
    decline_reason = Column(String(100))

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        # One live assignment per rider per job: re-offering the same rider
        # after they declined should be an explicit new row, not an update.
        UniqueConstraint("job_id", "agent_id", "wave", name="uq_delivery_assignment_attempt"),
        Index("ix_delivery_assignments_job_id", "job_id"),
        Index("ix_delivery_assignments_agent_id", "agent_id"),
    )

    job = relationship("DeliveryJob", back_populates="assignments")
    agent = relationship("DeliveryAgent")


class DeliveryJobEvent(Base):
    """Append-only event log for a job. INSERT-ONLY.

    The database revokes UPDATE and DELETE on this table (see the migration),
    so an accidental mutation fails loudly instead of corrupting history.
    """

    __tablename__ = "delivery_job_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False)

    # e.g. JOB_CREATED, DISPATCH_STARTED, OFFER_SENT, RIDER_ASSIGNED,
    # EXCEPTION_LOGGED, DISPATCH_RESTARTED, PICKUP_CONFIRMED, IN_TRANSIT,
    # DELIVERED, FAILED, RETURNED
    event_type = Column(String(60), nullable=False)
    # Status the job moved *into*, when the event implies one.
    to_status = Column(Enum(DeliveryJobStatus, native_enum=False))

    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="SET NULL"))
    actor_role = Column(String(30))

    # Wave number, assignment id, OTP-verified flag, etc. Kept flexible
    # precisely so new event types never need a schema change.
    payload = Column(JSONB)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (Index("ix_delivery_job_events_job_id", "job_id"),)

    job = relationship("DeliveryJob", back_populates="events")
    actor_user = relationship("User")


class FulfillmentSettlement(Base):
    """Money for one fulfillment (PRD F1/F3).

    Field names mirror the margin calculator's Delivery Log columns so the
    workbook can be driven from the database rather than maintained by hand:

        fee_collected, rider_payout, incentive_paid, payment_fee,
        contribution, margin_pct
    """

    __tablename__ = "fulfillment_settlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fulfillment_id = Column(
        UUID(as_uuid=True), ForeignKey("fulfillments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Only the FORWARD job contributes to customer-facing revenue; a RETURN leg
    # is a cost. Kept separate so the two can be reported independently.
    job_id = Column(UUID(as_uuid=True), ForeignKey("delivery_jobs.id", ondelete="SET NULL"))

    fee_collected = Column(Numeric(12, 2), nullable=False, default=0)
    rider_payout = Column(Numeric(12, 2), nullable=False, default=0)
    incentive_paid = Column(Numeric(12, 2), nullable=False, default=0)
    payment_fee = Column(Numeric(12, 2), nullable=False, default=0)
    partner_cost = Column(Numeric(12, 2), nullable=False, default=0)
    waiting_fee = Column(Numeric(12, 2), nullable=False, default=0)
    # Denormalised so the Zone Summary tab is a plain SUM rather than a
    # per-row computation. contribution = fee_collected - rider_payout
    #                                      - incentive_paid - payment_fee
    #                                      - partner_cost - waiting_fee
    contribution = Column(Numeric(12, 2), nullable=False, default=0)
    margin_pct = Column(Numeric(6, 4))
    currency = Column(String(3), nullable=False, default="KES")

    settled_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    fulfillment = relationship("Fulfillment", back_populates="settlement")


class JobSettlement(Base):
    """Per-attempt money, so a failed retry does not mask its own cost."""

    __tablename__ = "job_settlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)

    fee_collected = Column(Numeric(12, 2), nullable=False, default=0)
    rider_payout = Column(Numeric(12, 2), nullable=False, default=0)
    incentive_paid = Column(Numeric(12, 2), nullable=False, default=0)
    payment_fee = Column(Numeric(12, 2), nullable=False, default=0)
    partner_cost = Column(Numeric(12, 2), nullable=False, default=0)
    waiting_fee = Column(Numeric(12, 2), nullable=False, default=0)
    contribution = Column(Numeric(12, 2), nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    job = relationship("DeliveryJob", back_populates="settlement")