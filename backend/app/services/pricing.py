"""Delivery pricing and profitability engine.

Pure functions over the technical specification's formulas (§5,6,7,8,10,
§12,20). No database, no I/O: the caller supplies the inputs and persists the
result. That keeps every arithmetic rule testable without infrastructure, which
matters because these numbers decide whether Ekshop makes money.

Three decisions are deliberately *configuration*, not code, so the team can
change their mind without a deployment (§15 requires exactly that):

- **Which distance the customer pays for.** The specification prices the
  customer on ``D_mc`` while paying the rider on ``D_rm + D_mc``. With the
  specified rates that makes every delivery under ~4 km loss-making, because the
  rider's trip to collect is charged entirely to Ekshop. Set
  ``charge_rider_detour_to_customer=True`` and the customer pays for the whole
  rider movement, which is the only variant tested that is profitable at every
  distance. **This is questionnaire Q23 and it is a business decision, so it is
  a flag here rather than an assumption in the formula.**
- Every rate, floor, band and multiplier in ``PricingConfig``.
- Whether the exception-cost allowance is applied per delivery.

All arithmetic is :class:`~decimal.Decimal`. Floats are never used for money: a
binary float cannot represent 0.10 exactly, and a fee that is off by a
centimehundred times a day is a reconciliation problem forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Optional

MONEY = Decimal("0.01")
RATE = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _rate(value: Decimal) -> Decimal:
    return Decimal(value).quantize(RATE, rounding=ROUND_HALF_UP)


class ServiceLevel(str, Enum):
    standard = "standard"
    priority = "priority"
    express = "express"


class PricingStatus(str, Enum):
    """§12 verdicts. `LOSS_MAKING` is a recommendation, never an automatic reject."""

    healthy = "HEALTHY"
    positive_low_margin = "POSITIVE_LOW_MARGIN"
    loss_making = "LOSS_MAKING"


class RecommendedAction(str, Enum):
    """§12 /11 decision ladder, in the order the specification lists them."""

    normal = "NORMAL"
    optional_incentive = "OPTIONAL_INCENTIVE"
    merchant_subsidy = "MERCHANT_SUBSIDY"
    basket_building = "BASKET_BUILDING"
    batching = "BATCHING"
    alternative_fulfilment = "ALTERNATIVE_FULFILMENT"
    customer_pays_actual = "CUSTOMER_PAYS_ACTUAL"
    ekshop_logistics_unavailable = "EKS_HOP_LOGISTICS_UNAVAILABLE"
    manual_quote = "MANUAL_QUOTE"


@dataclass(frozen=True)
class WeightBand:
    max_kg: Optional[Decimal]  # None = open-ended top band
    multiplier: Decimal


@dataclass(frozen=True)
class SurgeBand:
    max_ratio: Optional[Decimal]
    multiplier: Decimal


@dataclass(frozen=True)
class PricingConfig:
    """Every tunable from15. Defaults are the specification's MVP values.

    Note these are the *specified* values, which the questionnaire shows produce
    a loss on deliveries under roughly 4 km. They are defaults, not
    recommendations; change them here or in the admin once Q23 is answered.
    """

    #5 customer price
    base_fare: Decimal = Decimal("80")
    customer_distance_rate: Decimal = Decimal("25")
    minimum_delivery_fare: Decimal = Decimal("120")

    #6 rider payout
    rider_base_fare: Decimal = Decimal("60")
    rider_distance_rate: Decimal = Decimal("15")
    minimum_rider_payout: Decimal = Decimal("100")
    waiting_grace_minutes: Decimal = Decimal("5")
    waiting_rate_per_minute: Decimal = Decimal("2")

    #7 weight bands, ascending. `None` means "no upper bound".
    weight_bands: tuple[WeightBand, ...] = (
        WeightBand(Decimal("5"), Decimal("1.00")),
        WeightBand(Decimal("10"), Decimal("1.10")),
        WeightBand(Decimal("20"), Decimal("1.25")),
    )
    #7 gives ">20 kg -> manual / special quote" with no formula, so there is
    # deliberately no multiplier band above 20 kg: the engine refuses instead of
    # inventing a price.
    manual_quote_above_kg: Optional[Decimal] = Decimal("20")

    # A.7 service-level multipliers
    service_multipliers: dict[ServiceLevel, Decimal] = field(
        default_factory=lambda: {
            ServiceLevel.standard: Decimal("1.00"),
            ServiceLevel.priority: Decimal("1.15"),
            ServiceLevel.express: Decimal("1.30"),
        }
    )

    #8 surge bands: <=1 -> 1.00, >1..2 -> 1.15, >2..3 -> 1.30, >3 -> 1.50.
    # The customer never sees more than `customer_surge_cap`; beyond that the
    # pressure is expressed as a rider incentive instead (B.2).
    surge_bands: tuple[SurgeBand, ...] = (
        SurgeBand(Decimal("1"), Decimal("1.00")),
        SurgeBand(Decimal("2"), Decimal("1.15")),
        SurgeBand(Decimal("3"), Decimal("1.30")),
        #8's ">3 -> 1.50" has no upper bound, so this band is open-ended.
        SurgeBand(None, Decimal("1.50")),
    )
    customer_surge_cap: Decimal = Decimal("1.30")
    max_customer_price: Optional[Decimal] = Decimal("500")  # D#1

    #12 profitability
    target_contribution: Decimal = Decimal("0.15")  # A.8 suggests 15-20%
    payment_cost_rate: Decimal = Decimal("0.015")  # PLACEHOLDER -- D#8 says measure
    failure_probability: Decimal = Decimal("0.08")  # B.4 example
    average_failure_cost: Decimal = Decimal("250")  # B.4 example

    #11 delivery/basket ratio thresholds
    ratio_incentive: Decimal = Decimal("0.10")
    ratio_subsidy: Decimal = Decimal("0.20")
    ratio_basket_building: Decimal = Decimal("0.30")
    ratio_intervention: Decimal = Decimal("0.40")

    #10.1 merchant subsidy caps
    maximum_delivery_subsidy: Optional[Decimal] = None
    free_delivery_threshold: Optional[Decimal] = None

    # Q23. False = the specification as written: the customer pays for D_mc only
    # and Ekshop absorbs the rider's detour. True = the customer pays for the
    # whole rider movement, which is the only profitable variant tested.
    charge_rider_detour_to_customer: bool = False

    def weight_multiplier(self, package_weight_kg: Optional[Decimal]) -> Optional[Decimal]:
        """§7 lookup. `None` when the order needs a manual quote."""
        if package_weight_kg is None:
            return Decimal("1.00")
        if self.manual_quote_above_kg is not None and package_weight_kg > self.manual_quote_above_kg:
            return None
        for band in self.weight_bands:
            if band.max_kg is None or package_weight_kg <= band.max_kg:
                return band.multiplier
        return None  # pragma: no cover - unreachable while manual_quote_above_kg is set

    def surge_multiplier(self, supply_ratio: Optional[Decimal]) -> Decimal:
        """§8. `supply_ratio = orders_waiting / available_riders`.

        Ratios above the highest band take that band's multiplier rather than
        falling back to 1.00:8 defines ">3 -> 1.50" with no upper limit, so a
        severe shortage must still attract riders. Returning 1.00 here would
        quietly drop the surge exactly when demand is worst.
        """
        if supply_ratio is None:
            return Decimal("1.00")
        for band in self.surge_bands:
            if band.max_ratio is not None and supply_ratio <= band.max_ratio:
                return band.multiplier
        return self.surge_bands[-1].multiplier

    def customer_surge_effective(
        self, supply_ratio: Optional[Decimal], service_multiplier: Decimal
    ) -> Decimal:
        """Surge as the customer sees it: capped, and never below 1."""
        raw = self.surge_multiplier(supply_ratio) * service_multiplier
        return min(raw, self.customer_surge_cap)


@dataclass(frozen=True)
class PricingInputs:
    """§3 required inputs, plus the4 distances and12 basket value."""

    basket_value: Decimal
    #4: the leg the customer is priced on by default...
    merchant_to_customer_km: Decimal
    # ...and the rider's trip to collect, which the rider is always paid for.
    rider_to_merchant_km: Decimal = Decimal("0")
    package_weight_kg: Optional[Decimal] = None
    service_level: ServiceLevel = ServiceLevel.standard
    supply_ratio: Optional[Decimal] = None
    merchant_subsidy: Decimal = Decimal("0")
    ekshop_subsidy: Decimal = Decimal("0")
    # Actual measured waiting,6. None before pickup.
    actual_wait_minutes: Optional[Decimal] = None


@dataclass(frozen=True)
class PricingResult:
    """The16 response, plus the20 status and decision."""

    #16
    merchant_to_customer_km: Decimal
    rider_to_merchant_km: Decimal
    total_km: Decimal
    charged_km: Decimal
    base_price: Decimal
    weight_multiplier: Decimal
    surge_multiplier: Decimal
    service_multiplier: Decimal
    customer_delivery_price: Decimal
    merchant_subsidy: Decimal
    ekshop_subsidy: Decimal
    customer_payment: Decimal
    rider_base_fare: Decimal
    rider_distance_payout: Decimal
    waiting_payout: Decimal
    chargeable_wait_minutes: Decimal
    rider_total_payout: Decimal
    payment_cost: Decimal
    expected_exception_cost: Decimal
    expected_delivery_cost: Decimal
    delivery_contribution: Decimal
    contribution_pct: Optional[Decimal]
    delivery_basket_ratio: Decimal
    minimum_economic_price: Decimal
    status: PricingStatus
    recommended_action: RecommendedAction
    reason: str
    requires_manual_quote: bool = False


class PricingError(ValueError):
    """Inputs that cannot produce a defensible price."""


def _dec(value, name: str) -> Decimal:
    try:
        return Decimal(value)
    except Exception as exc:  # noqa: BLE001
        raise PricingError(f"{name} must be a number, got {value!r}") from exc


def calculate(
    inputs: PricingInputs,
    config: Optional[PricingConfig] = None,
) -> PricingResult:
    """Price one delivery. Implements5,6,7,8,10,11,12 and20.

    Raises :class:`PricingError` rather than returning a guess when the inputs
    cannot produce a defensible price -- negative money, a missing distance, or
    an order over the manual-quote weight.
    """
    config = config or PricingConfig()

    basket_value = _dec(inputs.basket_value, "basket_value")
    d_mc = _dec(inputs.merchant_to_customer_km, "merchant_to_customer_km")
    d_rm = _dec(inputs.rider_to_merchant_km, "rider_to_merchant_km")
    merchant_subsidy = _dec(inputs.merchant_subsidy, "merchant_subsidy")
    ekshop_subsidy = _dec(inputs.ekshop_subsidy, "ekshop_subsidy")

    if basket_value < 0:
        raise PricingError("basket_value cannot be negative")
    if d_mc < 0 or d_rm < 0:
        raise PricingError("distances cannot be negative")
    if merchant_subsidy < 0 or ekshop_subsidy < 0:
        raise PricingError("a subsidy cannot be negative")

    d_total = d_rm + d_mc

    weight_multiplier = config.weight_multiplier(
        _dec(inputs.package_weight_kg, "package_weight_kg")
        if inputs.package_weight_kg is not None
        else None
    )
    if weight_multiplier is None:
        #7: ">20 kg -> manual / special quote". There is no formula, so the
        # engine refuses rather than inventing a price that would be wrong.
        return _manual_quote(inputs, config, d_mc, d_rm, d_total)

    service_multiplier = config.service_multipliers.get(
        inputs.service_level, Decimal("1.00")
    )

    # ──5 customer price ────────────────────────────────────────────────────
    base_price = _money(config.base_fare + config.customer_distance_rate * d_mc)
    surge_multiplier = config.customer_surge_effective(inputs.supply_ratio, service_multiplier)

    charged_km = d_total if config.charge_rider_detour_to_customer else d_mc
    # When the customer pays for the whole movement, the distance term is
    # recomputed on that distance rather than reusing the D_mc figure.
    price_distance = (
        config.base_fare + config.customer_distance_rate * charged_km
        if config.charge_rider_detour_to_customer
        else base_price
    )
    adjusted = price_distance * weight_multiplier * surge_multiplier
    customer_delivery_price = max(config.minimum_delivery_fare, _money(adjusted))

    ceiling_breached = (
        config.max_customer_price is not None
        and customer_delivery_price > config.max_customer_price
    )

    # ──10 subsidies change who pays, never the total (B.1) ─────────────────
    applied_merchant_subsidy = merchant_subsidy
    if (
        config.free_delivery_threshold is not None
        and basket_value >= config.free_delivery_threshold
    ):
        cap = config.maximum_delivery_subsidy
        applied_merchant_subsidy = (
            customer_delivery_price
            if cap is None
            else min(customer_delivery_price, cap)
        )
    if config.maximum_delivery_subsidy is not None and applied_merchant_subsidy > config.maximum_delivery_subsidy:
        applied_merchant_subsidy = config.maximum_delivery_subsidy

    total_subsidy = applied_merchant_subsidy + ekshop_subsidy
    customer_payment = _money(max(Decimal("0"), customer_delivery_price - total_subsidy))

    # ──6 rider payout, always on the full movement (§4) ────────────────────
    chargeable_wait = Decimal("0")
    if inputs.actual_wait_minutes is not None:
        chargeable_wait = max(
            Decimal("0"), _dec(inputs.actual_wait_minutes, "actual_wait_minutes") - config.waiting_grace_minutes
        )
    waiting_payout = _money(chargeable_wait * config.waiting_rate_per_minute)
    rider_base_fare = _money(config.rider_base_fare)
    rider_distance_payout = _money(config.rider_distance_rate * d_total)
    rider_total_payout = _money(
        max(
            config.minimum_rider_payout,
            (config.rider_base_fare + config.rider_distance_rate * d_total + waiting_payout)
            * weight_multiplier,
        )
    )

    # ──12 profitability, always on the gross price (B.1) ───────────────────
    payment_cost = _money(customer_delivery_price * config.payment_cost_rate)
    expected_exception_cost = _money(config.failure_probability * config.average_failure_cost)
    expected_delivery_cost = _money(
        rider_total_payout + payment_cost + expected_exception_cost
    )
    delivery_contribution = _money(
        customer_delivery_price - expected_delivery_cost
    )
    contribution_pct = (
        _rate(delivery_contribution / customer_delivery_price)
        if customer_delivery_price > 0
        else None
    )
    #12 writes minimum_economic_price as "... + target_delivery_contribution",
    # which reads like an addition but cannot be one: A.8 gives the target as a
    # margin *percentage* (15-20%), and adding 0.15 to a cost in shillings would
    # make the threshold meaningless. A margin of t on the price P means
    # P - cost >= t * P, i.e. P >= cost / (1 - t). That is what is computed here.
    target = config.target_contribution
    if target >= 1:
        raise PricingError("target_contribution is a margin rate and must be below 1")
    minimum_economic_price = (
        _money(expected_delivery_cost / (Decimal("1") - target))
        if expected_delivery_cost > 0
        else Decimal("0.00")
    )

    if delivery_contribution < 0:
        status = PricingStatus.loss_making
    elif contribution_pct is not None and contribution_pct < config.target_contribution:
        status = PricingStatus.positive_low_margin
    else:
        status = PricingStatus.healthy

    delivery_basket_ratio = (
        _rate(customer_delivery_price / basket_value) if basket_value > 0 else None
    )

    action, reason = _recommend(
        inputs=inputs,
        config=config,
        status=status,
        ratio=delivery_basket_ratio,
        ceiling_breached=ceiling_breached,
    )

    return PricingResult(
        merchant_to_customer_km=d_mc,
        rider_to_merchant_km=d_rm,
        total_km=_rate(d_total),
        charged_km=charged_km,
        base_price=_money(price_distance),
        weight_multiplier=weight_multiplier,
        surge_multiplier=surge_multiplier,
        service_multiplier=service_multiplier,
        customer_delivery_price=customer_delivery_price,
        merchant_subsidy=_money(applied_merchant_subsidy),
        ekshop_subsidy=_money(ekshop_subsidy),
        customer_payment=customer_payment,
        rider_base_fare=rider_base_fare,
        rider_distance_payout=rider_distance_payout,
        waiting_payout=waiting_payout,
        chargeable_wait_minutes=chargeable_wait,
        rider_total_payout=rider_total_payout,
        payment_cost=payment_cost,
        expected_exception_cost=expected_exception_cost,
        expected_delivery_cost=expected_delivery_cost,
        delivery_contribution=delivery_contribution,
        contribution_pct=contribution_pct,
        delivery_basket_ratio=delivery_basket_ratio if delivery_basket_ratio is not None else Decimal("0"),
        minimum_economic_price=minimum_economic_price,
        status=status,
        recommended_action=action,
        reason=reason,
    )


def _manual_quote(
    inputs: PricingInputs,
    config: PricingConfig,
    d_mc: Decimal,
    d_rm: Decimal,
    d_total: Decimal,
) -> PricingResult:
    """§7's ">20 kg -> manual / special quote" has no formula, so nothing is invented."""
    return PricingResult(
        merchant_to_customer_km=d_mc,
        rider_to_merchant_km=d_rm,
        total_km=_rate(d_total),
        charged_km=d_mc,
        base_price=Decimal("0"),
        weight_multiplier=Decimal("1.00"),
        surge_multiplier=Decimal("1.00"),
        service_multiplier=Decimal("1.00"),
        customer_delivery_price=Decimal("0"),
        merchant_subsidy=Decimal("0"),
        ekshop_subsidy=Decimal("0"),
        customer_payment=Decimal("0"),
        rider_base_fare=Decimal("0"),
        rider_distance_payout=Decimal("0"),
        waiting_payout=Decimal("0"),
        chargeable_wait_minutes=Decimal("0"),
        rider_total_payout=Decimal("0"),
        payment_cost=Decimal("0"),
        expected_exception_cost=Decimal("0"),
        expected_delivery_cost=Decimal("0"),
        delivery_contribution=Decimal("0"),
        contribution_pct=None,
        delivery_basket_ratio=Decimal("0"),
        minimum_economic_price=Decimal("0"),
        status=PricingStatus.loss_making,
        recommended_action=RecommendedAction.manual_quote,
        reason=(
            f"Package exceeds {config.manual_quote_above_kg} kg;7 requires a "
            f"manual quote and defines no formula"
        ),
        requires_manual_quote=True,
    )


def _recommend(
    *,
    inputs: PricingInputs,
    config: PricingConfig,
    status: PricingStatus,
    ratio: Optional[Decimal],
    ceiling_breached: bool,
) -> tuple[RecommendedAction, str]:
    """§12 for LOSS_MAKING,11 for a high delivery/basket ratio.

    The specification is explicit that the system "must not automatically reject
    a below-target order; it returns a pricing recommendation", so this never
    raises and never refuses an order.
    """
    if ceiling_breached:
        return (
            RecommendedAction.customer_pays_actual,
            f"Price exceeds the KES {config.max_customer_price} ceiling (D#1); "
            f"surge should be expressed as a rider incentive instead",
        )

    if status == PricingStatus.loss_making:
        return (
            RecommendedAction.basket_building,
            "Delivery contribution is negative;12 ladder starts at basket-building",
        )

    if ratio is None:
        return RecommendedAction.normal, "No basket value; no ratio-based action"

    if ratio > config.ratio_intervention:
        return (
            RecommendedAction.basket_building,
            f"Delivery is {ratio * 100:.0f}% of basket value (>40%);12 strong intervention",
        )
    if ratio > config.ratio_basket_building:
        return (
            RecommendedAction.merchant_subsidy,
            f"Delivery is {ratio * 100:.0f}% of basket value (>30%); recommend merchant subsidy + basket-building",
        )
    if ratio > config.ratio_subsidy:
        return (
            RecommendedAction.merchant_subsidy,
            f"Delivery is {ratio * 100:.0f}% of basket value (>20%); recommend merchant subsidy",
        )
    if ratio > config.ratio_incentive:
        return (
            RecommendedAction.optional_incentive,
            f"Delivery is {ratio * 100:.0f}% of basket value (>10%); optional incentive",
        )

    if status == PricingStatus.positive_low_margin:
        return (
            RecommendedAction.normal,
            f"Contribution is positive but below the "
            f"{config.target_contribution * 100:.0f}% target",
        )
    return RecommendedAction.normal, "Healthy delivery economics"