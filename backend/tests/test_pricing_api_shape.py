"""The16 pricing response must match the specified shape.

The specification gives a literal example response. If our field names drift from
it, a client built against the document breaks silently -- JSON does not error on
an unexpected field, it just omits what the reader expected.

Asserted without a database: the shape lives in the schema layer, so that is
where a mismatch would actually be.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal as D

from app.schemas.pricing_admin import PricingResponse

SPEC_EXAMPLE = {
    "order_id": "ORD-12345",
    "distance": {
        "rider_to_merchant_km": 2.1,
        "merchant_to_customer_km": 5.2,
        "total_km": 7.3,
    },
    "customer": {
        "base_price": 210,
        "surge_multiplier": 1.0,
        "merchant_subsidy": 50,
        "ekshop_subsidy": 0,
        "amount_to_pay": 160,
    },
    "rider": {
        "base_payout": 60,
        "distance_payout": 109.5,
        "waiting_payout": 0,
        "total_payout": 169.5,
    },
    "profitability": {
        "expected_delivery_cost": 176,
        "delivery_contribution": 34,
        "delivery_basket_ratio": 0.32,
        "status": "HEALTHY",
    },
    "recommendation": {
        "action": "MERCHANT_SUBSIDY",
        "reason": "HIGH_DELIVERY_BASKET_RATIO",
    },
}

_schema = PricingResponse.model_json_schema()
_DEFS = _schema.get("$defs", {})


def resolve(ref: str):
    """Follow a `$ref` into $defs and return the referenced schema."""
    return _DEFS[ref.rsplit("/", 1)[-1]]


def flatten(schema, prefix="", seen=None):
    """Every dotted field path in a schema, following `$ref`s."""
    seen = seen or set()
    out = set()
    for name, spec in (schema.get("properties") or {}).items():
        path = f"{prefix}{name}"
        if "$ref" in spec:
            target = spec["$ref"].rsplit("/", 1)[-1]
            if target not in seen:
                seen.add(target)
                out |= flatten(resolve(spec["$ref"]), f"{path}.", seen)
        else:
            out.add(path)
    return out


def test_every_documented_field_is_present():
    documented = flatten(SPEC_EXAMPLE)
    ours = flatten(_schema)
    assert not (documented - ours), f"missing from the response: {documented - ours}"


def test_fields_the_spec_text_requires_are_present():
    """§16's literal example is abbreviated. These are named in16/§17 and14
    and are needed for the response to be honest about how the price was reached.
    """
    ours = flatten(_schema)
    for field in (
        "pricing_version",              #17
        "distance_is_approximate",      #3.2
        "requires_manual_quote",        #7
        "calculated_at",
        "customer.weight_multiplier",   #7
        "customer.surge_multiplier",    #8
        "customer.service_multiplier",  #9
        "customer.delivery_price",      # gross, distinct from amount_to_pay
        "rider.chargeable_wait_minutes",  #6
        "profitability.payment_cost",
        "profitability.expected_exception_cost",
        "profitability.contribution_pct",
        "profitability.minimum_economic_price",  #12
    ):
        assert field in ours, f"missing {field}"


def test_gross_price_and_amount_paid_are_separate():
    """§10/B.1: a subsidy changes who pays, not the total. Collapsing these two
    is how a subsidy gets reported as lost revenue."""
    ours = flatten(_schema)
    assert "customer.delivery_price" in ours
    assert "customer.amount_to_pay" in ours


def test_approximate_distance_is_visible_to_the_client():
    """§3.2 compliance has to be checkable by whoever receives the quote, not
    only by someone reading the audit table later."""
    assert "distance_is_approximate" in _schema["properties"]


def test_a_spec_shaped_response_validates():
    response = PricingResponse(
        order_id="11111111-1111-1111-1111-111111111111",
        pricing_version="DELIVERY_V1_2026_10",
        distance_is_approximate=False,
        requires_manual_quote=False,
        distance={
            "rider_to_merchant_km": D("2.1"),
            "merchant_to_customer_km": D("5.2"),
            "total_km": D("7.3"),
        },
        customer={
            "base_price": D("210"),
            "weight_multiplier": D("1.00"),
            "surge_multiplier": D("1.00"),
            "service_multiplier": D("1.00"),
            "delivery_price": D("210"),
            "merchant_subsidy": D("50"),
            "ekshop_subsidy": D("0"),
            "amount_to_pay": D("160"),
        },
        rider={
            "base_fare": D("60"),
            "distance_payout": D("109.50"),
            "waiting_payout": D("0"),
            "chargeable_wait_minutes": D("0"),
            "total_payout": D("169.50"),
        },
        profitability={
            "payment_cost": D("3.15"),
            "expected_exception_cost": D("20"),
            "expected_delivery_cost": D("192.65"),
            "delivery_contribution": D("17.35"),
            "contribution_pct": D("0.0826"),
            "delivery_basket_ratio": D("0.32"),
            "minimum_economic_price": D("226.65"),
            "status": "HEALTHY",
        },
        recommendation={"action": "MERCHANT_SUBSIDY", "reason": "HIGH_DELIVERY_BASKET_RATIO"},
        calculated_at=datetime.now(timezone.utc),
    )
    assert response.customer.amount_to_pay == D("160")
    assert response.customer.delivery_price == D("210")
    assert response.distance.total_km == D("7.3")


def test_the_schema_is_json_serialisable():
    assert isinstance(json.dumps(_schema), str)


def test_money_survives_a_json_round_trip_exactly():
    """A float round-trip turns KES 162.50 into 162.49999999999997. The schema
    allows Decimal to serialise as a string, which is what keeps it exact."""
    dumped = PricingResponse(
        order_id="11111111-1111-1111-1111-111111111111",
        pricing_version="DELIVERY_V1_2026_10",
        distance_is_approximate=False,
        requires_manual_quote=False,
        distance={
            "rider_to_merchant_km": D("2.1"),
            "merchant_to_customer_km": D("3.3"),
            "total_km": D("5.4"),
        },
        customer={
            "base_price": D("162.50"),
            "weight_multiplier": D("1.00"),
            "surge_multiplier": D("1.00"),
            "service_multiplier": D("1.00"),
            "delivery_price": D("162.50"),
            "merchant_subsidy": D("0"),
            "ekshop_subsidy": D("0"),
            "amount_to_pay": D("162.50"),
        },
        rider={
            "base_fare": D("60"),
            "distance_payout": D("81.00"),
            "waiting_payout": D("0"),
            "chargeable_wait_minutes": D("0"),
            "total_payout": D("141.00"),
        },
        profitability={
            "payment_cost": D("2.44"),
            "expected_exception_cost": D("20"),
            "expected_delivery_cost": D("163.44"),
            "delivery_contribution": D("-0.94"),
            "contribution_pct": D("-0.0058"),
            "delivery_basket_ratio": D("0.1625"),
            "minimum_economic_price": D("192.28"),
            "status": "LOSS_MAKING",
        },
        recommendation={"action": "BASKET_BUILDING", "reason": "negative contribution"},
        calculated_at=datetime.now(timezone.utc),
    ).model_dump_json()
    assert "162.50" in dumped, "a Decimal must serialise exactly, not via a float"
    assert D("162.50") == D(json.loads(dumped)["customer"]["delivery_price"])