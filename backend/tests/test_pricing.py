"""The pricing engine must reproduce the specification's own worked examples.

Every assertion here traces to a numbered section of
`ekshop_technical_specification.md`. If the spec and the code disagree, this
file is where it shows up.
"""
from decimal import Decimal as D

import pytest

from app.services.pricing import (
    PricingConfig,
    PricingError,
    PricingInputs,
    PricingStatus,
    RecommendedAction,
    ServiceLevel,
    calculate,
)


def price(km, **kwargs):
    inputs = {
        "basket_value": D("1000"),
        "merchant_to_customer_km": D(str(km)),
    }
    inputs.update(kwargs)
    return calculate(PricingInputs(**inputs))


# --- §5 customer price ---------------------------------------------------------

@pytest.mark.parametrize(
    "km,expected",
    [
        (1, "120"),  # 80 + 25*1 = 105, floored to the 120 minimum
        (2, "130"),
        (3, "155"),
        (5, "205"),
        (7, "255"),
        (10, "330"),
    ],
)
def test_spec_distance_table(km, expected):
    """§5 publishes this exact table."""
    assert price(km).customer_delivery_price == D(expected)


def test_minimum_fare_floors_the_short_case():
    result = price(1)
    assert result.base_price == D("105.00")
    assert result.customer_delivery_price == D("120.00")


# --- §6 rider payout -----------------------------------------------------------

def test_spec_worked_example_pays_175():
    """§6: rider 2 km out, 5 km delivery, 10 min wait -> KES 175."""
    result = price(5, rider_to_merchant_km=D("2"), actual_wait_minutes=D("10"))
    assert result.rider_total_payout == D("175.00")
    assert result.rider_base_fare == D("60.00")
    assert result.rider_distance_payout == D("105.00")  # 15 x 7
    assert result.waiting_payout == D("10.00")  # (10 - 5 grace) x 2
    assert result.chargeable_wait_minutes == D("5")
    assert result.total_km == D("7.0000")


def test_waiting_grace_is_excluded():
    result = price(5, actual_wait_minutes=D("5"))
    assert result.chargeable_wait_minutes == D("0")
    assert result.waiting_payout == D("0.00")


def test_minimum_rider_payout_floor():
    assert price("0.5").rider_total_payout == D("100.00")


def test_rider_is_paid_on_the_full_movement():
    """§4: the customer price ignores the detour, the rider payout does not."""
    near = price(3, rider_to_merchant_km=D("0"))
    far = price(3, rider_to_merchant_km=D("5"))
    assert far.customer_delivery_price == near.customer_delivery_price
    assert far.rider_total_payout > near.rider_total_payout


# --- Q23: the open pricing decision, implemented as a flag ---------------------

@pytest.mark.parametrize("km", [1, 2, 3, 5, 7, 10, 15])
def test_charging_the_detour_is_profitable_at_every_distance(km):
    """Q23. Without this the specification loses money under ~4 km."""
    as_specified = price(km, rider_to_merchant_km=D("2"))
    with_detour = calculate(
        PricingInputs(
            basket_value=D("1000"),
            merchant_to_customer_km=D(str(km)),
            rider_to_merchant_km=D("2"),
        ),
        PricingConfig(charge_rider_detour_to_customer=True),
    )
    assert with_detour.contribution_pct > as_specified.contribution_pct
    assert with_detour.status == PricingStatus.healthy
    assert with_detour.charged_km == D(km) + 2


@pytest.mark.parametrize("km", [1, 2, 3])
def test_specification_as_written_loses_money_at_short_range(km):
    """The finding that makes Q23 urgent. If this ever starts passing, the
    economics changed and the questionnaire needs revisiting."""
    assert price(km, rider_to_merchant_km=D("2")).status == PricingStatus.loss_making


# --- §12 profitability --------------------------------------------------------

def test_specified_parameters_only_reach_target_from_about_10km():
    assert price(5, rider_to_merchant_km=D("2")).status == PricingStatus.positive_low_margin
    assert price(10, rider_to_merchant_km=D("2")).status == PricingStatus.healthy


def test_minimum_economic_price_yields_the_target_margin():
    """§12 writes it as an addition; A.8 makes the target a percentage, so it is
    cost / (1 - target). Adding 0.15 shillings would be meaningless."""
    result = price(5, rider_to_merchant_km=D("2"))
    implied = (result.minimum_economic_price - result.expected_delivery_cost) / result.minimum_economic_price
    assert abs(implied - D("0.15")) <= D("0.0002")


def test_healthy_iff_price_covers_the_minimum_economic_price():
    healthy = price(10, rider_to_merchant_km=D("2"))
    assert healthy.customer_delivery_price >= healthy.minimum_economic_price


def test_target_contribution_must_be_a_rate():
    with pytest.raises(PricingError):
        calculate(
            PricingInputs(basket_value=D("1000"), merchant_to_customer_km=D("5")),
            PricingConfig(target_contribution=D("1.5")),
        )


# --- §7 weight -----------------------------------------------------------------

@pytest.mark.parametrize(
    "kg,multiplier",
    [(0, "1.00"), (5, "1.00"), (5.1, "1.10"), (10, "1.10"), (10.1, "1.25"), (20, "1.25")],
)
def test_weight_bands(kg, multiplier):
    assert price(5, package_weight_kg=D(kg)).weight_multiplier == D(multiplier)


def test_weight_multiplier_raises_the_price():
    assert price(5, package_weight_kg=D("10")).customer_delivery_price == D("225.50")


def test_over_20kg_requires_a_manual_quote():
    """§7 says 'manual / special quote' and gives no formula, so nothing is invented."""
    result = price(5, package_weight_kg=D("25"))
    assert result.requires_manual_quote is True
    assert result.customer_delivery_price == D("0")
    assert result.recommended_action == RecommendedAction.manual_quote


# --- §8 surge ------------------------------------------------------------------

@pytest.mark.parametrize(
    "ratio,multiplier",
    [(0.5, "1.00"), (1, "1.00"), (1.5, "1.15"), (2, "1.15"), (2.5, "1.30"), (3, "1.30")],
)
def test_surge_bands(ratio, multiplier):
    assert price(5, supply_ratio=D(str(ratio))).surge_multiplier == D(multiplier)


def test_surge_above_the_top_band_keeps_the_highest_multiplier():
    """A ratio above 3 must take 1.50, not fall back to 1.00 -- otherwise the
    surge vanishes exactly when demand is worst."""
    assert price(5, supply_ratio=D("10")).surge_multiplier == D("1.30")  # capped for the customer
    unbounded = PricingConfig(customer_surge_cap=D("10"))
    result = calculate(
        PricingInputs(basket_value=D("1000"), merchant_to_customer_km=D("5"), supply_ratio=D("10")),
        unbounded,
    )
    assert result.surge_multiplier == D("1.50")


def test_customer_surge_is_capped():
    """§8 / D#1: the customer never sees more than 1.30."""
    result = price(10, supply_ratio=D("10"), service_level=ServiceLevel.express)
    assert result.surge_multiplier == D("1.30")


# --- A.7 service levels --------------------------------------------------------

@pytest.mark.parametrize(
    "level,multiplier",
    [(ServiceLevel.standard, "1.00"), (ServiceLevel.priority, "1.15"), (ServiceLevel.express, "1.30")],
)
def test_service_level_multipliers(level, multiplier):
    assert price(10, service_level=level).service_multiplier == D(multiplier)


def test_express_price():
    assert price(10, service_level=ServiceLevel.express).customer_delivery_price == D("429.00")


# --- §10 / B.1 subsidies -------------------------------------------------------

def test_subsidy_changes_who_pays_not_the_total():
    result = price(5, merchant_subsidy=D("50"))
    assert result.customer_delivery_price == D("205.00")
    assert result.customer_payment == D("155.00")
    # Contribution must use the gross, or a subsidy would flatter the margin.
    assert result.delivery_contribution == D("205.00") - result.expected_delivery_cost


def test_subsidy_larger_than_the_price_floors_the_customer_at_zero():
    result = price(5, merchant_subsidy=D("500"))
    assert result.customer_payment == D("0.00")
    assert result.customer_delivery_price == D("205.00")
    assert result.delivery_contribution == D("46.92")


def test_three_way_split():
    result = price(5, merchant_subsidy=D("100"), ekshop_subsidy=D("50"))
    assert result.customer_payment == D("55.00")


def test_free_delivery_threshold():
    config = PricingConfig(free_delivery_threshold=D("1500"), maximum_delivery_subsidy=D("200"))
    above = calculate(PricingInputs(basket_value=D("1600"), merchant_to_customer_km=D("5")), config)
    assert above.merchant_subsidy == D("200.00")
    assert above.customer_payment == D("5.00")
    below = calculate(PricingInputs(basket_value=D("1250"), merchant_to_customer_km=D("5")), config)
    assert below.merchant_subsidy == D("0.00")
    assert below.customer_payment == D("205.00")


# --- §11 the delivery/basket ratio ladder --------------------------------------

@pytest.mark.parametrize(
    "basket,action",
    [
        (3000, RecommendedAction.normal),
        (2000, RecommendedAction.optional_incentive),
        (1000, RecommendedAction.merchant_subsidy),
        (500, RecommendedAction.basket_building),
    ],
)
def test_ratio_action_ladder(basket, action):
    assert price(5, basket_value=D(basket)).recommended_action == action


def test_ratio_value():
    assert price(5, basket_value=D("1000")).delivery_basket_ratio == D("0.2050")


# --- §12 the system never auto-rejects ------------------------------------------

def test_absurd_order_returns_a_recommendation_not_a_rejection():
    result = calculate(
        PricingInputs(
            basket_value=D("100"),
            merchant_to_customer_km=D("1"),
            rider_to_merchant_km=D("20"),
        )
    )
    assert isinstance(result.recommended_action, RecommendedAction)


# --- input validation ----------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [
        {"basket_value": D("-1"), "merchant_to_customer_km": D("1")},
        {"basket_value": D("100"), "merchant_to_customer_km": D("-5")},
        {"basket_value": D("100"), "merchant_to_customer_km": D("1"), "merchant_subsidy": D("-1")},
    ],
)
def test_bad_input_is_refused(kwargs):
    with pytest.raises(PricingError):
        calculate(PricingInputs(**kwargs))


def test_zero_basket_does_not_divide_by_zero():
    result = calculate(PricingInputs(basket_value=D("0"), merchant_to_customer_km=D("5")))
    assert result.delivery_basket_ratio == D("0")


def test_decimal_arithmetic_is_exact():
    """A binary float cannot represent 0.10; 3.3 km must price to exactly 162.50."""
    assert price("3.3", rider_to_merchant_km=D("0")).customer_delivery_price == D("162.50")
    assert price("3.3", rider_to_merchant_km=D("0")).delivery_contribution.as_tuple().exponent == -2


# --- configurability -----------------------------------------------------------

def test_configuration_overrides_are_honoured():
    config = PricingConfig(
        base_fare=D("40"),
        customer_distance_rate=D("10"),
        minimum_delivery_fare=D("50"),
        rider_base_fare=D("30"),
        rider_distance_rate=D("8"),
        minimum_rider_payout=D("40"),
    )
    result = calculate(
        PricingInputs(basket_value=D("1000"), merchant_to_customer_km=D("5")), config
    )
    assert result.customer_delivery_price == D("90.00")
    assert result.rider_total_payout == D("70.00")