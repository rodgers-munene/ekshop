"""Tests for the cost-based delivery pricing model.

Everything here runs against pure functions — no database, no fixtures — because
the pricing model is deliberately built to be decidable from its inputs alone.
"""
import inspect
import json
import random
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.delivery import DeliveryRateSettings, PricingModel
from app.services.delivery_pricing import (
    COUNTY_REGIONS,
    REGION_ADJACENCY,
    DeliveryPoint,
    DistanceBand,
    calculate_delivery_fee_from_cart_total,
    get_region,
    parse_weight_kg,
    quote_delivery_fee,
    regions_are_adjacent,
    resolve_band,
    sum_cart_weight,
)

COUNTY_DATA = Path(__file__).resolve().parents[1] / "app" / "data" / "kenya_administrative_units.json"


def make_settings(**overrides):
    """A settings object carrying the model's real column defaults.

    Read off the table rather than retyped, so that changing a default in the
    model can't silently leave these tests asserting against stale numbers.
    """
    values = {
        column.name: column.default.arg
        for column in DeliveryRateSettings.__table__.columns
        if column.default is not None and not callable(column.default.arg)
    }
    values.update(overrides)
    return SimpleNamespace(**values)


NAIROBI_WARD = uuid.uuid4()
NAIROBI_SUBCOUNTY = uuid.uuid4()
OTHER_NAIROBI_WARD = uuid.uuid4()
OTHER_NAIROBI_SUBCOUNTY = uuid.uuid4()

BUYER = DeliveryPoint(county="Nairobi", subcounty_id=NAIROBI_SUBCOUNTY, ward_id=NAIROBI_WARD)


def quote(shop_points, weight="0", **setting_overrides):
    return quote_delivery_fee(
        BUYER,
        shop_points,
        Decimal(weight),
        make_settings(**setting_overrides),
    )


# ── The bugs that prompted the rewrite ────────────────────────────────────────

def test_legacy_model_charges_more_for_a_smaller_cart():
    """Documents the original defect, straight from the two checkout screenshots.

    A Ksh 870 cart was quoted 72. Removing an Ksh 850 item RAISED delivery to 87.
    """
    assert calculate_delivery_fee_from_cart_total(Decimal("870")) == Decimal("72")
    assert calculate_delivery_fee_from_cart_total(Decimal("20")) == Decimal("87")


def test_legacy_model_has_a_cliff_at_the_800_boundary():
    """One extra shilling of goods cut delivery by more than half."""
    assert calculate_delivery_fee_from_cart_total(Decimal("799")) == Decimal("150")
    assert calculate_delivery_fee_from_cart_total(Decimal("800")) == Decimal("66")


def test_cost_based_fee_ignores_cart_value_entirely():
    """The core fix: cart value is not an input, so there is no cliff to fall off.

    Asserted against the signature rather than by varying a price, because the
    point is that no price can be passed in at all.
    """
    accepted = set(inspect.signature(quote_delivery_fee).parameters)
    assert accepted == {"buyer", "shop_points", "cart_weight_kg", "settings"}


def test_adding_items_never_lowers_the_fee():
    """The monotonicity property, fuzzed over random multi-seller carts."""
    rng = random.Random(20260917)
    counties = list(COUNTY_REGIONS.keys())

    for _ in range(300):
        shops = {}
        weight = Decimal("0")
        previous = Decimal("0")

        for _ in range(rng.randint(1, 6)):
            shops[uuid.uuid4()] = DeliveryPoint(county=rng.choice(counties))
            weight += Decimal(rng.randint(0, 8))

            current = quote(shops, weight=str(weight)).total
            assert current >= previous, f"fee fell from {previous} to {current}"
            previous = current


# ── Distance bands ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "shop, expected",
    [
        (DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD), DistanceBand.same_ward),
        (DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, OTHER_NAIROBI_WARD), DistanceBand.same_subcounty),
        (DeliveryPoint("Nairobi", OTHER_NAIROBI_SUBCOUNTY, OTHER_NAIROBI_WARD), DistanceBand.same_county),
        (DeliveryPoint("Kiambu"), DistanceBand.same_region),          # both Nairobi Metro
        (DeliveryPoint("Nyeri"), DistanceBand.adjacent_region),       # Central borders Nairobi Metro
        (DeliveryPoint("Mandera"), DistanceBand.different_region),    # North Eastern does not
        (DeliveryPoint(None), DistanceBand.unknown_origin),
    ],
)
def test_band_resolution(shop, expected):
    assert resolve_band(BUYER, shop) == expected


def test_band_falls_back_to_county_when_ward_data_is_missing():
    """Shops and addresses predate the ward tables; missing ids must not crash."""
    assert resolve_band(DeliveryPoint("Nairobi"), DeliveryPoint("Nairobi")) == DistanceBand.same_county


def test_bands_are_priced_in_ascending_order_by_default():
    settings = make_settings()
    ladder = [
        settings.same_ward_fee,
        settings.same_subcounty_fee,
        settings.same_county_fee,
        settings.same_region_fee,
        settings.adjacent_region_fee,
        settings.different_region_fee,
    ]
    values = [Decimal(v) for v in ladder]
    assert values == sorted(values), "further away must never be cheaper"


# ── County and region coverage ────────────────────────────────────────────────

def test_every_selectable_county_maps_to_a_region():
    """Buyers can pick any of the 47 seeded counties.

    An unmapped one silently lands on the most expensive band, which is exactly
    how Makueni and Marsabit were being overcharged before this change.
    """
    seeded = set(json.loads(COUNTY_DATA.read_text(encoding="utf-8")).keys())
    unmapped = sorted(seeded - set(COUNTY_REGIONS))
    assert unmapped == [], f"counties with no region: {unmapped}"


def test_makueni_and_marsabit_are_mapped():
    assert get_region("Makueni") == "Eastern"
    assert get_region("Marsabit") == "North Eastern"


@pytest.mark.parametrize("written", ["Nyeri", "NYERI", "nyeri", "  nYeRi  "])
def test_county_region_lookup_ignores_case_and_padding(written):
    """Sellers type their county by hand; the live data holds every casing."""
    assert get_region(written) == "Central"


def test_same_county_is_recognised_whatever_the_casing():
    band = resolve_band(DeliveryPoint("nyeri"), DeliveryPoint("NYERI"))
    assert band == DistanceBand.same_county


def test_unplaceable_county_is_not_charged_as_a_long_haul():
    """A county name we don't recognise is unknown, not far.

    20 live shops had "Nyeri Town" in the county column, so Nyeri buyers were
    quoted the countrywide band for a trip across town. An origin we can't place
    must price as unknown_origin, which sits mid-ladder.
    """
    band = resolve_band(DeliveryPoint("Nyeri"), DeliveryPoint("Nyeri Town"))
    assert band == DistanceBand.unknown_origin

    settings = make_settings()
    assert Decimal(settings.unknown_origin_fee) < Decimal(settings.different_region_fee)


def test_makueni_is_a_short_hop_from_nairobi_not_a_countrywide_one():
    """The regression this fixes: Machakos borders Makueni."""
    assert resolve_band(BUYER, DeliveryPoint("Makueni")) == DistanceBand.adjacent_region


def test_region_adjacency_is_symmetric():
    for region, neighbours in REGION_ADJACENCY.items():
        for neighbour in neighbours:
            assert region in REGION_ADJACENCY[neighbour], f"{region}/{neighbour} disagree"


def test_region_adjacency_only_references_real_regions():
    known = set(COUNTY_REGIONS.values())
    for region, neighbours in REGION_ADJACENCY.items():
        assert region in known
        assert neighbours <= known


def test_a_region_is_not_adjacent_to_itself():
    assert not regions_are_adjacent("Coast", "Coast")


# ── Multi-seller carts ────────────────────────────────────────────────────────

def test_multi_seller_cart_is_charged_one_journey_at_the_longest_leg():
    settings = make_settings()
    near, far = uuid.uuid4(), uuid.uuid4()
    shops = {
        near: DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD),  # same ward
        far: DeliveryPoint("Nyeri"),                                      # adjacent region
    }
    result = quote(shops)
    assert result.charged_band == DistanceBand.adjacent_region
    # The dearer leg alone, not the sum of both.
    assert result.total == Decimal(settings.adjacent_region_fee)
    assert result.total < Decimal(settings.adjacent_region_fee) + Decimal(settings.same_ward_fee)


def test_extra_nearby_sellers_do_not_add_to_the_fee():
    """The explicit pricing decision: one journey, regardless of pickup count."""
    shops = {uuid.uuid4(): DeliveryPoint("Nyeri")}
    alone = quote(shops).total

    for _ in range(3):
        shops[uuid.uuid4()] = DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD)
    assert quote(shops).total == alone


def test_empty_cart_falls_back_to_the_unknown_origin_band():
    result = quote({})
    assert result.charged_band == DistanceBand.unknown_origin


# ── Weight ────────────────────────────────────────────────────────────────────

def test_weight_within_the_allowance_costs_nothing_extra():
    shops = {uuid.uuid4(): DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD)}
    assert quote(shops, weight="10").total == quote(shops, weight="0").total


def test_weight_above_the_allowance_is_surcharged_per_kg():
    settings = make_settings()
    shops = {uuid.uuid4(): DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD)}
    result = quote(shops, weight="15")  # 5kg over, at 12/kg
    assert result.billable_weight_kg == Decimal("5")
    assert result.weight_surcharge == Decimal("60")
    assert result.total == Decimal(settings.same_ward_fee) + Decimal("60")


def test_weight_surcharge_is_capped():
    shops = {uuid.uuid4(): DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD)}
    result = quote(shops, weight="5000", max_delivery_fee="99999.00")
    assert result.weight_surcharge == Decimal("600")


@pytest.mark.parametrize("raw", [None, "", "  ", "not a number", "-4", "0"])
def test_unset_or_junk_weights_count_as_zero(raw):
    """Missing seller data must never invent a surcharge."""
    assert parse_weight_kg(raw) == Decimal("0")


def test_sum_cart_weight_multiplies_by_quantity():
    assert sum_cart_weight([("2.5", 4), (None, 10), ("1", 2)]) == Decimal("12")


# ── Bounds and rounding ───────────────────────────────────────────────────────

def test_floor_protects_the_cheapest_possible_delivery():
    shops = {uuid.uuid4(): DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD)}
    result = quote(shops, same_ward_fee="10.00")
    assert result.floor_applied is True
    assert result.total == Decimal("60")


def test_cap_limits_a_heavy_long_haul_quote():
    shops = {uuid.uuid4(): DeliveryPoint("Mandera")}
    result = quote(shops, weight="200")
    assert result.cap_applied is True
    assert result.total == Decimal("800")


def test_totals_round_up_to_the_nearest_five():
    shops = {uuid.uuid4(): DeliveryPoint("Nairobi", NAIROBI_SUBCOUNTY, NAIROBI_WARD)}
    assert quote(shops, same_ward_fee="101.00").total == Decimal("105")
    assert quote(shops, same_ward_fee="100.00").total == Decimal("100")


def test_cost_based_is_not_enabled_by_default():
    """Deploying this migration must not change what buyers are charged."""
    assert make_settings().pricing_model == PricingModel.cart_total.value
