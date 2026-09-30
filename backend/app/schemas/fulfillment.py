"""Pydantic schemas for the fulfillment state machine.

Money is `Decimal` throughout and serialised as a string, matching the existing
commerce convention (`orders.total` is `VARCHAR(20)`). A float would reintroduce
exactly the rounding error the settlement arithmetic exists to avoid.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.fulfillment import (
    AssignmentStatus,
    DeliveryJobStatus,
    DeliveryJobType,
    FulfillmentMode,
    FulfillmentPayer,
    FulfillmentStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── events and assignments ─────────────────────────────────────────────────────


class JobEventRead(ORMModel):
    id: UUID
    event_type: str
    to_status: Optional[str]
    actor_user_id: Optional[UUID]
    actor_agent_id: Optional[UUID]
    actor_role: Optional[str]
    payload: Optional[dict]
    notes: Optional[str]
    created_at: datetime


class AssignmentRead(ORMModel):
    id: UUID
    job_id: UUID
    agent_id: UUID
    wave: int
    status: AssignmentStatus
    payout_estimate: Optional[Decimal]
    distance_km: Optional[Decimal]
    offered_at: Optional[datetime]
    expires_at: Optional[datetime]
    responded_at: Optional[datetime]
    decline_reason: Optional[str]


# ── jobs ──────────────────────────────────────────────────────────────────────


class DeliveryJobRead(ORMModel):
    id: UUID
    fulfillment_id: UUID
    external_reference: str
    attempt: int
    job_type: DeliveryJobType
    status: DeliveryJobStatus
    agent_id: Optional[UUID]
    distance_km: Optional[Decimal]
    quoted_fee: Optional[Decimal]
    failure_code: Optional[str]
    failure_reason: Optional[str]
    otp_expires_at: Optional[datetime]
    otp_verified_at: Optional[datetime]
    override_reason: Optional[str]
    created_at: datetime
    dispatch_requested_at: Optional[datetime]
    accepted_at: Optional[datetime]
    at_pickup_at: Optional[datetime]
    picked_up_at: Optional[datetime]
    in_transit_at: Optional[datetime]
    delivered_at: Optional[datetime]
    settled_at: Optional[datetime]
    failed_at: Optional[datetime]
    closed_at: Optional[datetime]


class DeliveryJobDetail(DeliveryJobRead):
    """A job with the history and offer trail attached."""

    events: List[JobEventRead] = Field(default_factory=list)
    assignments: List[AssignmentRead] = Field(default_factory=list)


class JobSettlementRead(ORMModel):
    id: UUID
    job_id: UUID
    fee_collected: Decimal
    rider_payout: Decimal
    incentive_paid: Decimal
    payment_fee: Decimal
    partner_cost: Decimal
    waiting_fee: Decimal
    contribution: Decimal
    created_at: datetime


class FulfillmentSettlementRead(ORMModel):
    id: UUID
    fulfillment_id: UUID
    job_id: Optional[UUID]
    fee_collected: Decimal
    rider_payout: Decimal
    incentive_paid: Decimal
    payment_fee: Decimal
    partner_cost: Decimal
    waiting_fee: Decimal
    contribution: Decimal
    margin_pct: Optional[Decimal]
    currency: str
    settled_at: Optional[datetime]


# ── fulfillment ───────────────────────────────────────────────────────────────


class FulfillmentRead(ORMModel):
    id: UUID
    order_id: UUID
    mode: FulfillmentMode
    # Derived from the current job, never stored. Present in the response so a
    # client can render state without reimplementing the state machine.
    status: FulfillmentStatus
    payer: FulfillmentPayer
    payer_split_pct: Optional[Decimal]
    self_rider_name: Optional[str]
    self_rider_phone: Optional[str]
    quoted_fee: Optional[Decimal]
    close_reason: Optional[str]
    created_at: datetime
    confirmed_at: Optional[datetime]
    closed_at: Optional[datetime]
    settled_at: Optional[datetime]


class FulfillmentDetail(FulfillmentRead):
    jobs: List[DeliveryJobDetail] = Field(default_factory=list)
    settlement: Optional[FulfillmentSettlementRead] = None


class FulfillmentListResponse(BaseModel):
    items: List[FulfillmentRead]
    total: int
    page: int
    page_size: int


# ── requests ──────────────────────────────────────────────────────────────────


class FulfillmentCreate(BaseModel):
    """Merchant asks for an order to be delivered."""

    order_id: UUID
    mode: FulfillmentMode = FulfillmentMode.ekshop
    payer: FulfillmentPayer = FulfillmentPayer.customer
    payer_split_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)
    self_rider_name: Optional[str] = Field(default=None, max_length=150)
    self_rider_phone: Optional[str] = Field(default=None, max_length=20)
    quoted_fee: Optional[Decimal] = Field(default=None, ge=0)

    @field_validator("self_rider_phone")
    @classmethod
    def _phone_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.replace(" ", "").replace("-", "")
        if not cleaned.startswith("+") or not cleaned[1:].isdigit():
            raise ValueError("Phone must be E.164, e.g. +254712345678")
        return cleaned

    @field_validator("self_rider_name")
    @classmethod
    def _name_required_for_self(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Rider name cannot be blank")
        return v

    @model_validator(mode="after")
    def _self_delivery_needs_a_rider(self) -> "FulfillmentCreate":
        """A self-delivery with nobody named cannot produce a trackable timeline.

        Enforced here as well as in the service: at the HTTP boundary this is a
        malformed request (422), not a state conflict (409), and the service
        keeps its own check for non-HTTP callers.
        """
        if self.mode == FulfillmentMode.self_ and not (
            self.self_rider_name and self.self_rider_phone
        ):
            raise ValueError(
                "Self-delivery requires the merchant's rider name and phone"
            )
        if self.payer == FulfillmentPayer.split and self.payer_split_pct is None:
            raise ValueError("A split payer requires payer_split_pct")
        return self


class AssignmentCreate(BaseModel):
    """Offer a job to a specific rider."""

    agent_id: UUID
    wave: int = Field(default=1, ge=1, le=10)
    payout_estimate: Optional[Decimal] = Field(default=None, ge=0)
    distance_km: Optional[Decimal] = Field(default=None, ge=0)
    ttl_seconds: int = Field(default=90, ge=10, le=600)


class AssignmentRespond(BaseModel):
    status: AssignmentStatus
    decline_reason: Optional[str] = Field(default=None, max_length=100)


class JobTransitionRequest(BaseModel):
    """Advance a job to a new state.

    The service validates the transition; this schema only carries the intent.
    `otp` is required when `validate_otp` is set (marking a delivery complete).
    """

    status: DeliveryJobStatus
    event_type: Optional[str] = Field(default=None, max_length=60)
    notes: Optional[str] = None
    validate_otp: bool = False
    otp: Optional[str] = Field(default=None, min_length=4, max_length=10)


class IssueOtpRequest(BaseModel):
    ttl_minutes: int = Field(default=30, ge=1, le=1440)


class IssueOtpResponse(BaseModel):
    """The plaintext code. Returned once, never stored, never readable again."""

    otp: str
    expires_at: datetime


class ReasonRequest(BaseModel):
    """Retry, return, close and override all require a reason.

    A reason is not decoration: it is the only record of why a customer waited
    longer than they should have.
    """

    reason: str = Field(min_length=3, max_length=500)


class OverrideRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    status: DeliveryJobStatus = DeliveryJobStatus.cancelled
    notes: Optional[str] = None


class JobSettlementCreate(BaseModel):
    fee_collected: Decimal = Field(default=Decimal("0"), ge=0)
    rider_payout: Decimal = Field(default=Decimal("0"), ge=0)
    incentive_paid: Decimal = Field(default=Decimal("0"), ge=0)
    payment_fee: Optional[Decimal] = Field(default=None, ge=0)
    partner_cost: Decimal = Field(default=Decimal("0"), ge=0)
    waiting_fee: Decimal = Field(default=Decimal("0"), ge=0)
    payment_fee_pct: Optional[Decimal] = Field(default=None, ge=0, le=1)


class FulfillmentQuoteRequest(BaseModel):
    """Placeholder for the fee quote. The schedule is still an open team
    decision (questionnaire Q1/Q2), so this endpoint is not implemented yet
    rather than shipping placeholder numbers to customers."""

    order_id: UUID
