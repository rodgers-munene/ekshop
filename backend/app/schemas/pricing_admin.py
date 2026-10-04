"""Pydantic schemas for the pricing API (§16) and admin parameters (§15)."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.pricing_config import ParameterValueType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- §16 the required pricing response ------------------------------------------


class PricingDistance(BaseModel):
    """§16 names these three explicitly. `total_km` is the whole rider movement,
    which is what the rider is paid on."""

    rider_to_merchant_km: Decimal
    merchant_to_customer_km: Decimal
    total_km: Decimal


class PricingCustomer(BaseModel):
    base_price: Decimal
    weight_multiplier: Decimal
    surge_multiplier: Decimal
    service_multiplier: Decimal
    # The gross price before subsidies. What the delivery is worth.
    delivery_price: Decimal
    merchant_subsidy: Decimal
    ekshop_subsidy: Decimal
    # What the buyer actually hands over. Different from delivery_price whenever a
    # subsidy applies, and conflating the two is how a subsidy gets mistaken for
    # lost revenue.
    amount_to_pay: Decimal


class PricingRider(BaseModel):
    base_fare: Decimal
    distance_payout: Decimal
    waiting_payout: Decimal
    chargeable_wait_minutes: Decimal
    total_payout: Decimal


class PricingProfitability(BaseModel):
    payment_cost: Decimal
    expected_exception_cost: Decimal
    expected_delivery_cost: Decimal
    delivery_contribution: Decimal
    contribution_pct: Optional[Decimal]
    delivery_basket_ratio: Decimal
    minimum_economic_price: Decimal
    status: str


class PricingRecommendation(BaseModel):
    """§12: the engine returns a recommendation and never auto-rejects."""

    action: str
    reason: str


class PricingResponse(BaseModel):
    """The §16 response shape."""

    order_id: UUID
    pricing_version: str
    # A quote built on straight-line distance is not a defensible firm price
    # (§3.2). Surfaced so the caller can decide, rather than buried in an audit
    # table nobody reads.
    distance_is_approximate: bool
    requires_manual_quote: bool
    distance: PricingDistance
    customer: PricingCustomer
    rider: PricingRider
    profitability: PricingProfitability
    recommendation: PricingRecommendation
    calculated_at: datetime


class PricingQuoteRequest(BaseModel):
    """Quote for an order.

    Distances are supplied by the caller, which is expected to have measured them
    with the road-distance provider. Making them explicit rather than derived
    here keeps the geodesic fallback out of the pricing path by construction: a
    caller that only has straight-line numbers has to say so via
    `distance_is_approximate`.
    """

    order_id: UUID
    merchant_to_customer_km: Decimal = Field(ge=0)
    rider_to_merchant_km: Decimal = Field(default=Decimal("0"), ge=0)
    supply_ratio: Optional[Decimal] = Field(default=None, ge=0)
    merchant_subsidy: Optional[Decimal] = Field(default=None, ge=0)
    ekshop_subsidy: Decimal = Field(default=Decimal("0"), ge=0)
    distance_source: Optional[str] = Field(default=None, max_length=20)
    # The caller asserts this. It defaults to True, so a caller who forgets to
    # set it cannot accidentally present a geodesic quote as firm.
    distance_is_approximate: bool = True


class PricingCalculationRead(ORMModel):
    """A stored calculation (§17). Read-only -- these rows are append-only."""

    id: UUID
    order_id: UUID
    fulfillment_id: Optional[UUID]
    pricing_version: str
    reason: str
    customer_delivery_price: Decimal
    customer_amount_paid: Decimal
    rider_total_payout: Decimal
    expected_contribution: Decimal
    contribution_pct: Optional[Decimal]
    pricing_status: str
    pricing_decision: str
    distance_source: Optional[str]
    distance_is_approximate: bool
    requires_manual_quote: bool
    created_at: datetime


# --- §15 admin parameters -------------------------------------------------------


class PricingParameterRead(ORMModel):
    key: str
    value: str
    value_type: ParameterValueType
    description: Optional[str]
    spec_reference: Optional[str]
    is_commercial_decision: bool
    updated_at: datetime


class PricingParameterUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=80)
    reason: str = Field(
        default="",
        max_length=500,
        description=(
            "Why the value changed. Recorded alongside it because a rate edit "
            "with no explanation cannot be reasoned about later."
        ),
    )


class PricingParameterListResponse(BaseModel):
    items: list[PricingParameterRead]
    # Shown prominently: these are placeholders, not agreed numbers.
    placeholder_count: int
    pricing_version: str


class ParameterChangeLogRead(ORMModel):
    key: str
    previous_value: str
    new_value: str
    changed_at: datetime
    changed_by_user_id: Optional[UUID]