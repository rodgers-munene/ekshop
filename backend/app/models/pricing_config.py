"""Admin-configurable pricing parameters and the pricing audit record.

Two specification requirements that need persistence:

§15 -- "All parameters below must be editable without a code deployment."
  The rates live in :class:`PricingParameters` rows rather than in a dataclass
  default, so an admin change takes effect on the next quote and is itself
  recorded.

§17 -- "Every pricing calculation is stored", with a version, and "Historical
  orders retain their original calculation -- never recalculate historical
  economics with current rules."
  :class:`PricingCalculation` is append-only and carries every input and every
  parameter value used, so the arithmetic can be re-derived long after the
  schedule has moved on.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ParameterValueType(str, enum.Enum):
    """How a parameter's string value should be interpreted and validated."""

    money = "money"
    rate = "rate"
    integer = "integer"
    boolean = "boolean"
    json = "json"


class PricingParameter(Base):
    """One editable pricing parameter (§15).

    A name/value table rather than columns, because the set of parameters is
    expected to grow (per-zone overrides in v1.1, per-vehicle rates) and because
    it makes every value auditable: `updated_by_user_id` and `updated_at` record
    who changed what and when.
    """

    __tablename__ = "pricing_parameters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(80), nullable=False, unique=True)
    # Stored as text because one column holds money, rates, integers, booleans
    # and JSON. The value is parsed strictly on read, so a malformed value fails
    # loudly instead of silently becoming zero.
    value = Column(String(80), nullable=False)
    value_type = Column(
        Enum(ParameterValueType, native_enum=False),
        default=ParameterValueType.money,
        nullable=False,
        server_default="money",
    )
    description = Column(Text)
    # Which specification section justifies the value, so an admin editing it can
    # see the reasoning without opening the document.
    spec_reference = Column(String(20))
    # True for the values that are commercial decisions rather than rates, so the
    # admin UI can distinguish "finance tunes this" from "this needs a decision".
    is_commercial_decision = Column(Boolean, default=False, nullable=False, server_default="0")
    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "value_type IN ('money','rate','integer','boolean','json')",
            name="ck_pricing_parameters_value_type",
        ),
    )


class PricingCalculation(Base):
    """One immutable pricing calculation (§17).

    Deliberately a separate table from the fulfillment rather than more columns
    on it: one order may be priced several times -- a quote at checkout, a
    re-quote at dispatch, and again for every retry -- and each of those is a
    separate fact worth keeping.

    The `order_id`/`fulfillment_id` foreign keys are RESTRICT, and the table has
    an append-only trigger. An audit trail that can be edited, or that vanishes
    when its parent is deleted, is not an audit trail.
    """

    __tablename__ = "pricing_calculations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    fulfillment_id = Column(
        UUID(as_uuid=True), ForeignKey("fulfillments.id", ondelete="RESTRICT")
    )
    # e.g. DELIVERY_V1_2026_10. A schedule change creates a new version and never
    # rewrites existing rows.
    pricing_version = Column(String(40), nullable=False)
    # quote | dispatch_requote | retry | manual. Together with the version this
    # is unique, so re-pricing the same order for the same reason is refused
    # rather than silently duplicating the audit trail.
    reason = Column(String(40), nullable=False, server_default="quote")

    # Provenance of the distance (§3.2,4). Storing the source and the
    # approximate flag makes3.2 compliance verifiable after the fact: a price
    # built on straight-line distance can be identified years later.
    merchant_lat = Column(Numeric(9, 6))
    merchant_lng = Column(Numeric(9, 6))
    customer_lat = Column(Numeric(9, 6))
    customer_lng = Column(Numeric(9, 6))
    rider_lat = Column(Numeric(9, 6))
    rider_lng = Column(Numeric(9, 6))
    merchant_to_customer_km = Column(Numeric(10, 3), nullable=False)
    rider_to_merchant_km = Column(Numeric(10, 3), nullable=False, server_default="0")
    distance_source = Column(String(20))
    distance_is_approximate = Column(Boolean, default=False, nullable=False, server_default="0")

    # Order inputs (§3.1,7,9)
    basket_value = Column(Numeric(12, 2), nullable=False)
    package_weight_kg = Column(Numeric(8, 3))
    service_level = Column(String(20))
    supply_ratio = Column(Numeric(8, 3))

    # Every parameter value used, so the arithmetic can be re-derived even after
    # the schedule changes. This is the point of17.
    base_fare = Column(Numeric(12, 2), nullable=False)
    customer_distance_rate = Column(Numeric(12, 2), nullable=False)
    customer_weight_multiplier = Column(Numeric(6, 4), nullable=False, server_default="1")
    customer_surge_multiplier = Column(Numeric(6, 4), nullable=False, server_default="1")
    customer_delivery_price = Column(Numeric(12, 2), nullable=False)
    merchant_subsidy = Column(Numeric(12, 2), nullable=False, server_default="0")
    ekshop_subsidy = Column(Numeric(12, 2), nullable=False, server_default="0")
    customer_amount_paid = Column(Numeric(12, 2), nullable=False, server_default="0")

    rider_base_fare = Column(Numeric(12, 2), nullable=False)
    rider_distance_rate = Column(Numeric(12, 2), nullable=False)
    rider_distance_payout = Column(Numeric(12, 2), nullable=False)
    waiting_payout = Column(Numeric(12, 2), nullable=False, server_default="0")
    chargeable_wait_minutes = Column(Numeric(8, 2), nullable=False, server_default="0")
    rider_total_payout = Column(Numeric(12, 2), nullable=False)

    payment_cost = Column(Numeric(12, 2), nullable=False, server_default="0")
    expected_exception_cost = Column(Numeric(12, 2), nullable=False, server_default="0")
    expected_delivery_cost = Column(Numeric(12, 2), nullable=False)
    expected_contribution = Column(Numeric(12, 2), nullable=False)
    contribution_pct = Column(Numeric(8, 4))
    delivery_basket_ratio = Column(Numeric(8, 4))
    minimum_economic_price = Column(Numeric(12, 2))

    pricing_status = Column(String(30), nullable=False)
    pricing_decision = Column(String(40), nullable=False)
    decision_reason = Column(Text)
    requires_manual_quote = Column(Boolean, default=False, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    order = relationship("Order")
    fulfillment = relationship("Fulfillment")

    __table_args__ = (
        UniqueConstraint("order_id", "reason", "pricing_version", name="uq_pricing_calculation"),
        Index("ix_pricing_calculations_order_id", "order_id"),
        Index("ix_pricing_calculations_fulfillment_id", "fulfillment_id"),
        Index("ix_pricing_calculations_pricing_version", "pricing_version"),
        Index("ix_pricing_calculations_status_created_at", "pricing_status", "created_at"),
        CheckConstraint(
            "pricing_status IN ('HEALTHY','POSITIVE_LOW_MARGIN','LOSS_MAKING')",
            name="ck_pricing_calculations_status",
        ),
    )