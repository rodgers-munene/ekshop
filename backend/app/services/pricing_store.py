"""Persistence for the pricing engine: admin parameters and the audit record.

Two jobs, both required by the specification:

§15 -- load :class:`PricingConfig` from the ``pricing_parameters`` table so rates
  can be changed by an admin without a deployment.

§17 -- persist every :class:`PricingResult` to ``pricing_calculations`` with the
  version it was calculated under, and never recompute a historical one.

The engine itself stays pure. This module is the only part that touches the
database, which keeps the arithmetic testable without infrastructure.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from app.models.commerce import Order
from app.models.pricing_config import (
    ParameterValueType,
    PricingCalculation,
    PricingParameter,
)
from app.services.pricing import (
    PricingConfig,
    PricingInputs,
    PricingResult,
    ServiceLevel,
    SurgeBand,
    WeightBand,
    calculate,
)

logger = logging.getLogger(__name__)

# Bumped when the schedule's *meaning* changes, not when a rate is edited.17
# expects a label like DELIVERY_V1_2026_10.
DEFAULT_PRICING_VERSION = "DELIVERY_V1_2026_10"

# Values used when a parameter row is missing or unparseable. They mirror
# PricingConfig's own defaults so a partially-seeded database still produces the
# specified prices rather than zeros.
FALLBACK: dict[str, str] = {
    "base_fare": "80",
    "customer_distance_rate": "25",
    "minimum_delivery_fare": "120",
    "rider_base_fare": "60",
    "rider_distance_rate": "15",
    "minimum_rider_payout": "100",
    "waiting_grace_minutes": "5",
    "waiting_rate_per_minute": "2",
    "manual_quote_above_kg": "20",
    "customer_surge_cap": "1.30",
    "max_customer_price": "500",
    "service_multiplier_standard": "1.00",
    "service_multiplier_priority": "1.15",
    "service_multiplier_express": "1.30",
    "target_contribution": "0.15",
    "payment_cost_rate": "0.015",
    "failure_probability": "0.08",
    "average_failure_cost": "250",
    "charge_rider_detour_to_customer": "false",
}


class PricingConfigError(RuntimeError):
    """A stored parameter cannot be turned into a usable configuration."""


def _parse(raw: str, value_type: str, key: str):
    """Parse a stored parameter strictly.

    A malformed value raises rather than defaulting to zero. A rate that quietly
    becomes 0 would make every delivery look free, and a money value that becomes
    0 would make every rider unpaid -- both worse than a failed request.
    """
    text = (raw or "").strip()
    try:
        if value_type == ParameterValueType.money.value:
            return Decimal(text)
        if value_type == ParameterValueType.rate.value:
            return Decimal(text)
        if value_type == ParameterValueType.integer.value:
            return int(Decimal(text))
        if value_type == ParameterValueType.boolean.value:
            lowered = text.lower()
            if lowered in ("true", "1", "yes", "on"):
                return True
            if lowered in ("false", "0", "no", "off"):
                return False
            raise ValueError(f"{text!r} is not a boolean")
        if value_type == ParameterValueType.json.value:
            return json.loads(text)
    except (InvalidOperation, ValueError, json.JSONDecodeError) as exc:
        raise PricingConfigError(
            f"Pricing parameter {key!r} has an unusable value {raw!r} "
            f"for type {value_type!r}: {exc}"
        ) from exc
    raise PricingConfigError(f"Pricing parameter {key!r} has an unknown type {value_type!r}")


def read_parameters(db: Session) -> dict[str, str]:
    """All stored parameters, with the specification's defaults for any gap."""
    values = dict(FALLBACK)
    for row in db.query(PricingParameter).all():
        values[row.key] = row.value
    return values


def load_config(db: Session) -> PricingConfig:
    """Build a :class:`PricingConfig` from the database.

    Falls back to the specification's documented values for any parameter that is
    absent, so a fresh or partially-seeded database still prices correctly rather
    than raising. A parameter that exists but cannot be parsed *does* raise --
    that is a real misconfiguration and should be visible.
    """
    values = read_parameters(db)
    types = {
        row.key: row.value_type.value
        for row in db.query(PricingParameter).all()
    }

    def typed(key: str):
        return _parse(values[key], types.get(key, _guess_type(key)), key)

    weight_bands = (
        WeightBand(Decimal("5"), Decimal("1.00")),
        WeightBand(Decimal("10"), Decimal("1.10")),
        WeightBand(Decimal("20"), Decimal("1.25")),
    )
    surge_bands = (
        SurgeBand(Decimal("1"), Decimal("1.00")),
        SurgeBand(Decimal("2"), Decimal("1.15")),
        SurgeBand(Decimal("3"), Decimal("1.30")),
        SurgeBand(None, Decimal("1.50")),
    )

    return PricingConfig(
        base_fare=typed("base_fare"),
        customer_distance_rate=typed("customer_distance_rate"),
        minimum_delivery_fare=typed("minimum_delivery_fare"),
        rider_base_fare=typed("rider_base_fare"),
        rider_distance_rate=typed("rider_distance_rate"),
        minimum_rider_payout=typed("minimum_rider_payout"),
        waiting_grace_minutes=Decimal(typed("waiting_grace_minutes")),
        waiting_rate_per_minute=typed("waiting_rate_per_minute"),
        weight_bands=weight_bands,
        manual_quote_above_kg=(
            Decimal(typed("manual_quote_above_kg"))
            if typed("manual_quote_above_kg") is not None
            else None
        ),
        service_multipliers={
            ServiceLevel.standard: typed("service_multiplier_standard"),
            ServiceLevel.priority: typed("service_multiplier_priority"),
            ServiceLevel.express: typed("service_multiplier_express"),
        },
        surge_bands=surge_bands,
        customer_surge_cap=typed("customer_surge_cap"),
        max_customer_price=(
            Decimal(typed("max_customer_price"))
            if typed("max_customer_price") not in ("", None)
            else None
        ),
        target_contribution=typed("target_contribution"),
        payment_cost_rate=typed("payment_cost_rate"),
        failure_probability=typed("failure_probability"),
        average_failure_cost=typed("average_failure_cost"),
        # Q23. The one switch that decides whether short deliveries make money.
        charge_rider_detour_to_customer=bool(typed("charge_rider_detour_to_customer")),
    )


def _guess_type(key: str) -> str:
    """Value type for a parameter with no row, inferred from its name."""
    if key.endswith("_enabled") or key.startswith("charge_"):
        return ParameterValueType.boolean.value
    if key.endswith("_minutes") or key.endswith("_kg"):
        return ParameterValueType.integer.value
    if "rate" in key or "multiplier" in key or "cap" in key or "probability" in key:
        return ParameterValueType.rate.value
    return ParameterValueType.money.value


def set_parameter(
    db: Session,
    key: str,
    value: str,
    *,
    updated_by_user_id: Optional[uuid.UUID] = None,
    commit: bool = True,
) -> PricingParameter:
    """Update one parameter, validating before saving.

    Validation happens on the way in so a bad value is rejected at the point of
    entry rather than at the next quote, where it would surface as a mysterious
    pricing failure.
    """
    row = db.query(PricingParameter).filter(PricingParameter.key == key).first()
    if row is None:
        raise PricingConfigError(
            f"Unknown pricing parameter {key!r}. Add it deliberately rather than "
            f"typo-creating a new one: an unrecognised key would be silently "
            f"ignored by the engine."
        )
    _parse(value, row.value_type.value, key)
    row.value = value
    row.updated_by_user_id = updated_by_user_id
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def _order_basket_value(order: Order) -> Decimal:
    """Basket value for the ratio.

    Taken from the order's subtotal rather than its total: the delivery fee is
    not part of what the customer spent on goods, and including it would make a
    high delivery price look like a high-value basket.
    """
    try:
        return Decimal(str(order.subtotal or "0"))
    except InvalidOperation:
        return Decimal("0")


def build_inputs(
    order: Order,
    *,
    merchant_to_customer_km: Decimal,
    rider_to_merchant_km: Decimal = Decimal("0"),
    supply_ratio: Optional[Decimal] = None,
    merchant_subsidy: Decimal = Decimal("0"),
    ekshop_subsidy: Decimal = Decimal("0"),
    actual_wait_minutes: Optional[Decimal] = None,
    distance_source: Optional[str] = None,
) -> PricingInputs:
    """Assemble the engine's inputs from an order and measured distances."""
    weight = order.package_weight_kg
    try:
        level = ServiceLevel(order.service_level)
    except (ValueError, TypeError):
        level = ServiceLevel.standard
    return PricingInputs(
        basket_value=_order_basket_value(order),
        merchant_to_customer_km=merchant_to_customer_km,
        rider_to_merchant_km=rider_to_merchant_km,
        package_weight_kg=Decimal(str(weight)) if weight is not None else None,
        service_level=level,
        supply_ratio=supply_ratio,
        merchant_subsidy=merchant_subsidy,
        ekshop_subsidy=ekshop_subsidy,
        actual_wait_minutes=actual_wait_minutes,
    )


def record_calculation(
    db: Session,
    order: Order,
    result: PricingResult,
    inputs: PricingInputs,
    *,
    reason: str = "quote",
    fulfillment_id: Optional[uuid.UUID] = None,
    pricing_version: str = DEFAULT_PRICING_VERSION,
    config: Optional[PricingConfig] = None,
    distance_source: Optional[str] = None,
    distance_is_approximate: bool = False,
    commit: bool = True,
) -> PricingCalculation:
    """Persist one calculation (§17).

    Every parameter value that affected the outcome is copied onto the row, not
    referenced. That is what makes17's promise possible: a schedule change in
    November cannot alter what the arithmetic was in October.
    """
    config = config or PricingConfig()

    def dec(value, default="0"):
        return Decimal(str(value if value is not None else default))

    row = PricingCalculation(
        order_id=order.id,
        fulfillment_id=fulfillment_id,
        pricing_version=pricing_version,
        reason=reason,
        merchant_lat=getattr(order.shop, "lat", None) if order.shop else None,
        merchant_lng=getattr(order.shop, "lng", None) if order.shop else None,
        merchant_to_customer_km=result.merchant_to_customer_km,
        rider_to_merchant_km=result.rider_to_merchant_km,
        distance_source=distance_source,
        distance_is_approximate=distance_is_approximate,
        basket_value=inputs.basket_value,
        package_weight_kg=dec(inputs.package_weight_kg, "0") if inputs.package_weight_kg is not None else None,
        service_level=inputs.service_level.value,
        supply_ratio=dec(inputs.supply_ratio, "0") if inputs.supply_ratio is not None else None,
        base_fare=config.base_fare,
        customer_distance_rate=config.customer_distance_rate,
        customer_weight_multiplier=result.weight_multiplier,
        customer_surge_multiplier=result.surge_multiplier,
        customer_delivery_price=result.customer_delivery_price,
        merchant_subsidy=result.merchant_subsidy,
        ekshop_subsidy=result.ekshop_subsidy,
        customer_amount_paid=result.customer_payment,
        rider_base_fare=config.rider_base_fare,
        rider_distance_rate=config.rider_distance_rate,
        rider_distance_payout=result.rider_distance_payout,
        waiting_payout=result.waiting_payout,
        chargeable_wait_minutes=result.chargeable_wait_minutes,
        rider_total_payout=result.rider_total_payout,
        payment_cost=result.payment_cost,
        expected_exception_cost=result.expected_exception_cost,
        expected_delivery_cost=result.expected_delivery_cost,
        expected_contribution=result.delivery_contribution,
        contribution_pct=result.contribution_pct,
        delivery_basket_ratio=result.delivery_basket_ratio,
        minimum_economic_price=result.minimum_economic_price,
        pricing_status=result.status.value,
        pricing_decision=result.recommended_action.value,
        decision_reason=result.reason,
        requires_manual_quote=result.requires_manual_quote,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def quote_order(
    db: Session,
    order: Order,
    *,
    merchant_to_customer_km: Decimal,
    rider_to_merchant_km: Decimal = Decimal("0"),
    supply_ratio: Optional[Decimal] = None,
    merchant_subsidy: Optional[Decimal] = None,
    ekshop_subsidy: Decimal = Decimal("0"),
    reason: str = "quote",
    pricing_version: str = DEFAULT_PRICING_VERSION,
    distance_source: Optional[str] = None,
    distance_is_approximate: bool = False,
    fulfillment_id: Optional[uuid.UUID] = None,
) -> tuple[PricingResult, PricingCalculation]:
    """Price an order, persist the calculation, and return both.

   14 price lock: when the order's price is already locked the stored figure is
    returned rather than recalculated, so a slow assignment or a moving rider can
    never change what the customer agreed to pay.
    """
    if order.delivery_price_locked and order.fulfillments:
        fulfillment = order.fulfillments[0]
        if fulfillment.delivery_price_gross is not None:
            existing = (
                db.query(PricingCalculation)
                .filter(PricingCalculation.fulfillment_id == fulfillment.id)
                .order_by(PricingCalculation.created_at.desc())
                .first()
            )
            if existing is not None:
                return _result_from_row(existing), existing

    config = load_config(db)
    # Merchant subsidy defaults to the shop's configured contribution (§10.1).
    if merchant_subsidy is None:
        shop = order.shop
        if shop is not None and shop.delivery_subsidy_enabled:
            merchant_subsidy = Decimal(str(shop.delivery_subsidy_amount or "0"))
        else:
            merchant_subsidy = Decimal("0")

    inputs = build_inputs(
        order,
        merchant_to_customer_km=merchant_to_customer_km,
        rider_to_merchant_km=rider_to_merchant_km,
        supply_ratio=supply_ratio,
        merchant_subsidy=merchant_subsidy,
        ekshop_subsidy=ekshop_subsidy,
    )
    result = calculate(inputs, config)
    row = record_calculation(
        db,
        order,
        result,
        inputs,
        reason=reason,
        fulfillment_id=fulfillment_id,
        pricing_version=pricing_version,
        config=config,
        distance_source=distance_source,
        distance_is_approximate=distance_is_approximate,
    )
    return result, row


def _result_from_row(row: PricingCalculation) -> PricingResult:
    """Rebuild an engine result from a stored calculation.

    Used by the price lock, so a locked quote is served from the record that
    produced it rather than recomputed under whatever the schedule is now.
    """
    from app.services.pricing import PricingStatus, RecommendedAction

    return PricingResult(
        merchant_to_customer_km=Decimal(str(row.merchant_to_customer_km)),
        rider_to_merchant_km=Decimal(str(row.rider_to_merchant_km)),
        total_km=Decimal(str(row.merchant_to_customer_km)) + Decimal(str(row.rider_to_merchant_km)),
        charged_km=Decimal(str(row.merchant_to_customer_km)),
        base_price=Decimal(str(row.base_fare)),
        weight_multiplier=Decimal(str(row.customer_weight_multiplier)),
        surge_multiplier=Decimal(str(row.customer_surge_multiplier)),
        service_multiplier=Decimal("1.00"),
        customer_delivery_price=Decimal(str(row.customer_delivery_price)),
        merchant_subsidy=Decimal(str(row.merchant_subsidy)),
        ekshop_subsidy=Decimal(str(row.ekshop_subsidy)),
        customer_payment=Decimal(str(row.customer_amount_paid)),
        rider_base_fare=Decimal(str(row.rider_base_fare)),
        rider_distance_payout=Decimal(str(row.rider_distance_payout)),
        waiting_payout=Decimal(str(row.waiting_payout)),
        chargeable_wait_minutes=Decimal(str(row.chargeable_wait_minutes)),
        rider_total_payout=Decimal(str(row.rider_total_payout)),
        payment_cost=Decimal(str(row.payment_cost)),
        expected_exception_cost=Decimal(str(row.expected_exception_cost)),
        expected_delivery_cost=Decimal(str(row.expected_delivery_cost)),
        delivery_contribution=Decimal(str(row.expected_contribution)),
        contribution_pct=Decimal(str(row.contribution_pct)) if row.contribution_pct is not None else None,
        delivery_basket_ratio=Decimal(str(row.delivery_basket_ratio or "0")),
        minimum_economic_price=Decimal(str(row.minimum_economic_price or "0")),
        status=PricingStatus(row.pricing_status),
        recommended_action=RecommendedAction(row.pricing_decision),
        reason=row.decision_reason or "",
        requires_manual_quote=row.requires_manual_quote,
    )