import enum
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.delivery import DeliveryRateSettings

# Counties grouped into logistics clusters for delivery pricing — grouped by
# real courier route proximity (e.g. Sendy/G4S zones), not official province
# boundaries, so neighboring commuter counties around Nairobi aren't priced
# like a cross-country shipment.
COUNTY_REGIONS: dict[str, str] = {
    # Nairobi Metro
    "Nairobi": "Nairobi Metro",
    "Kiambu": "Nairobi Metro",
    "Machakos": "Nairobi Metro",
    "Kajiado": "Nairobi Metro",
    "Murang'a": "Nairobi Metro",
    # Central
    "Nyeri": "Central",
    "Nyandarua": "Central",
    "Kirinyaga": "Central",
    # Coast
    "Mombasa": "Coast",
    "Kwale": "Coast",
    "Kilifi": "Coast",
    "Tana River": "Coast",
    "Lamu": "Coast",
    "Taita Taveta": "Coast",
    # Rift Valley North
    "Nakuru": "Rift Valley North",
    "Baringo": "Rift Valley North",
    "Laikipia": "Rift Valley North",
    "Nandi": "Rift Valley North",
    "Uasin Gishu": "Rift Valley North",
    "Trans Nzoia": "Rift Valley North",
    "Elgeyo Marakwet": "Rift Valley North",
    "West Pokot": "Rift Valley North",
    "Samburu": "Rift Valley North",
    "Turkana": "Rift Valley North",
    # Rift Valley South
    "Kericho": "Rift Valley South",
    "Bomet": "Rift Valley South",
    "Narok": "Rift Valley South",
    # Western
    "Kakamega": "Western",
    "Bungoma": "Western",
    "Busia": "Western",
    "Vihiga": "Western",
    # Nyanza
    "Kisumu": "Nyanza",
    "Siaya": "Nyanza",
    "Homa Bay": "Nyanza",
    "Migori": "Nyanza",
    "Kisii": "Nyanza",
    "Nyamira": "Nyanza",
    # Eastern
    "Embu": "Eastern",
    "Kitui": "Eastern",
    "Meru": "Eastern",
    "Tharaka-Nithi": "Eastern",
    "Isiolo": "Eastern",
    "Makueni": "Eastern",
    # North Eastern
    "Garissa": "North Eastern",
    "Wajir": "North Eastern",
    "Mandera": "North Eastern",
    "Marsabit": "North Eastern",
}

# Which regions share a border, as a courier actually drives it. Used to price a
# short cross-region hop (Nairobi -> Nyeri) below a genuine cross-country one
# (Nairobi -> Mandera). Declared one way and mirrored below, so the map can
# never disagree with itself.
_ADJACENT_REGION_PAIRS: tuple[tuple[str, str], ...] = (
    ("Nairobi Metro", "Central"),            # Kiambu/Murang'a <-> Nyeri/Nyandarua
    ("Nairobi Metro", "Eastern"),            # Machakos <-> Kitui/Makueni
    ("Nairobi Metro", "Rift Valley North"),  # Kiambu/Kajiado <-> Nakuru
    ("Nairobi Metro", "Rift Valley South"),  # Kajiado <-> Narok
    ("Nairobi Metro", "Coast"),              # Kajiado <-> Taita Taveta
    ("Central", "Eastern"),                  # Kirinyaga/Nyeri <-> Embu/Meru
    ("Central", "Rift Valley North"),        # Nyandarua <-> Nakuru/Laikipia
    ("Coast", "Eastern"),                    # Tana River <-> Kitui/Isiolo
    ("Coast", "North Eastern"),              # Tana River/Lamu <-> Garissa
    ("Eastern", "North Eastern"),            # Kitui/Isiolo <-> Garissa/Wajir
    ("Eastern", "Rift Valley North"),        # Isiolo/Meru <-> Samburu/Laikipia
    ("Rift Valley North", "Rift Valley South"),  # Nakuru <-> Kericho/Bomet
    ("Rift Valley North", "Western"),        # Trans Nzoia/Nandi <-> Bungoma
    ("Rift Valley North", "Nyanza"),         # Nandi <-> Kisumu
    ("Rift Valley South", "Nyanza"),         # Kericho <-> Kisii/Nyamira
    ("Western", "Nyanza"),                   # Busia/Vihiga <-> Siaya/Kisumu
)

REGION_ADJACENCY: dict[str, frozenset[str]] = {}
for _a, _b in _ADJACENT_REGION_PAIRS:
    REGION_ADJACENCY.setdefault(_a, set()).add(_b)      # type: ignore[union-attr]
    REGION_ADJACENCY.setdefault(_b, set()).add(_a)      # type: ignore[union-attr]
REGION_ADJACENCY = {k: frozenset(v) for k, v in REGION_ADJACENCY.items()}


# Matched case-insensitively: sellers type their county by hand, so the live
# data holds "NYERI" and "nyeri" alongside "Nyeri". Treating those as unmapped
# priced a local delivery as a countrywide one.
_COUNTY_REGIONS_FOLDED = {name.casefold(): region for name, region in COUNTY_REGIONS.items()}


def get_region(county: Optional[str]) -> Optional[str]:
    if not county:
        return None
    return _COUNTY_REGIONS_FOLDED.get(county.strip().casefold())


def regions_are_adjacent(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b or a == b:
        return False
    return b in REGION_ADJACENCY.get(a, frozenset())


def get_or_create_rate_settings(db: Session) -> DeliveryRateSettings:
    settings = db.query(DeliveryRateSettings).first()
    if settings:
        return settings

    settings = DeliveryRateSettings()
    db.add(settings)
    db.flush()
    return settings


def calculate_delivery_fee(
    buyer_county: Optional[str],
    shop_county: Optional[str],
    settings: DeliveryRateSettings,
) -> Decimal:
    if not shop_county:
        return Decimal(settings.unknown_origin_fee)

    if buyer_county and buyer_county.strip() == shop_county.strip():
        return Decimal(settings.same_county_fee)

    if get_region(buyer_county) is not None and get_region(buyer_county) == get_region(shop_county):
        return Decimal(settings.same_region_fee)

    return Decimal(settings.different_region_fee)


# Legacy pricing model, kept only as a rollback path for PricingModel.cart_total.
#
# Known-broken, deliberately unfixed: the fee is derived from cart value alone,
# so it is blind to distance AND non-monotonic — a cart crossing 800 drops from
# a flat 150 to 8.25% (66), meaning one extra shilling of goods cut delivery by
# 84. Do not extend this; cost_based below replaces it.
def calculate_delivery_fee_from_cart_total(cart_total: Decimal) -> Decimal:
    if cart_total >= 800:
        return (cart_total * Decimal("0.0825")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if cart_total >= 400:
        return Decimal("150")
    if cart_total >= 150:
        return Decimal("127")
    if cart_total >= 50:
        return Decimal("93")
    if cart_total >= 1:
        return Decimal("87")
    return Decimal("0")


# ── Cost-based pricing ────────────────────────────────────────────────────────
#
# The model checkout should be on. Unlike the two above it, cart value is not an
# input at all: a delivery costs what it costs to drive, so the fee is built from
# distance and weight only. Two properties hold by construction, and are pinned
# by tests in backend/tests/test_delivery_pricing.py:
#
#   1. Adding anything to a cart can never lower the fee. The charged distance
#      band can only move outward and weight only accumulates. The old model
#      broke this — a cart crossing 800 saw delivery fall from 150 to 66.
#   2. Two carts going to the same place from the same sellers are quoted the
#      same fee whether they hold Ksh 20 or Ksh 20,000 of goods.
#
# Per the pricing decision of 2026-09-17, a cart spanning several sellers is
# charged ONE journey — the most expensive leg — rather than per pickup. That
# keeps multi-seller carts affordable and is what buyers already expect today;
# the cost of extra pickups is absorbed deliberately.


class DistanceBand(str, enum.Enum):
    same_ward = "same_ward"
    same_subcounty = "same_subcounty"
    same_county = "same_county"
    same_region = "same_region"
    adjacent_region = "adjacent_region"
    different_region = "different_region"
    unknown_origin = "unknown_origin"


BAND_LABELS: dict[DistanceBand, str] = {
    DistanceBand.same_ward: "Within your ward",
    DistanceBand.same_subcounty: "Within your sub-county",
    DistanceBand.same_county: "Within your county",
    DistanceBand.same_region: "Nearby county",
    DistanceBand.adjacent_region: "Neighbouring region",
    DistanceBand.different_region: "Countrywide",
    DistanceBand.unknown_origin: "Seller location not set",
}

_BAND_SETTING_FIELDS: dict[DistanceBand, str] = {
    DistanceBand.same_ward: "same_ward_fee",
    DistanceBand.same_subcounty: "same_subcounty_fee",
    DistanceBand.same_county: "same_county_fee",
    DistanceBand.same_region: "same_region_fee",
    DistanceBand.adjacent_region: "adjacent_region_fee",
    DistanceBand.different_region: "different_region_fee",
    DistanceBand.unknown_origin: "unknown_origin_fee",
}


@dataclass(frozen=True)
class DeliveryPoint:
    """One end of a delivery leg, resolved down to whatever detail we hold.

    `ward_id` and `subcounty_id` are optional because both shops and addresses
    predate the ward-level geography tables; when they are missing the band
    simply resolves at county granularity instead of failing.
    """
    county: Optional[str] = None
    subcounty_id: Optional[uuid.UUID] = None
    ward_id: Optional[uuid.UUID] = None


@dataclass(frozen=True)
class ShopLeg:
    shop_id: Optional[uuid.UUID]
    shop_county: Optional[str]
    band: DistanceBand
    fee: Decimal


@dataclass(frozen=True)
class DeliveryQuote:
    total: Decimal
    charged_band: DistanceBand
    band_fee: Decimal
    weight_surcharge: Decimal
    billable_weight_kg: Decimal
    legs: tuple[ShopLeg, ...]
    floor_applied: bool
    cap_applied: bool

    @property
    def band_label(self) -> str:
        return BAND_LABELS[self.charged_band]


def resolve_band(buyer: DeliveryPoint, shop: DeliveryPoint) -> DistanceBand:
    """Classify how far a parcel travels, using the finest detail both ends share."""
    if not shop.county:
        return DistanceBand.unknown_origin

    if buyer.ward_id and shop.ward_id and buyer.ward_id == shop.ward_id:
        return DistanceBand.same_ward

    if buyer.subcounty_id and shop.subcounty_id and buyer.subcounty_id == shop.subcounty_id:
        return DistanceBand.same_subcounty

    buyer_county = (buyer.county or "").strip()
    shop_county = shop.county.strip()
    if buyer_county and buyer_county.casefold() == shop_county.casefold():
        return DistanceBand.same_county

    buyer_region = get_region(buyer_county)
    shop_region = get_region(shop_county)

    # A county we can't place is not the same as a county far away. Sellers type
    # this field by hand and the live data holds towns ("Nyeri Town") and
    # outright junk in it; falling through to different_region would charge the
    # dearest band for a trip that may well be local. Price it as unplaceable
    # instead, and let the admin county table surface it for correction.
    if not buyer_region or not shop_region:
        return DistanceBand.unknown_origin

    if buyer_region == shop_region:
        return DistanceBand.same_region
    if regions_are_adjacent(buyer_region, shop_region):
        return DistanceBand.adjacent_region

    return DistanceBand.different_region


def band_fee(band: DistanceBand, settings: DeliveryRateSettings) -> Decimal:
    return Decimal(getattr(settings, _BAND_SETTING_FIELDS[band]))


def parse_weight_kg(raw: Optional[str]) -> Decimal:
    """Product.weight_kg is a free-text column and is very often unset.

    Anything unparseable counts as zero rather than as a guessed default, so a
    seller who never filled the field can't have a surcharge invented for them.
    """
    if not raw:
        return Decimal("0")
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return value if value > 0 else Decimal("0")


def _round_up_to_5(value: Decimal) -> Decimal:
    return (value / 5).quantize(Decimal("1"), rounding=ROUND_CEILING) * 5


def quote_delivery_fee(
    buyer: DeliveryPoint,
    shop_points: dict[Optional[uuid.UUID], DeliveryPoint],
    cart_weight_kg: Decimal,
    settings: DeliveryRateSettings,
) -> DeliveryQuote:
    """Price one delivery journey for a whole cart.

    `shop_points` maps shop id -> that shop's location. The cart is charged for a
    single journey covering its most expensive leg, plus a surcharge on whatever
    cart weight exceeds the free allowance.
    """
    legs: list[ShopLeg] = []
    for shop_id, point in shop_points.items():
        band = resolve_band(buyer, point)
        legs.append(ShopLeg(shop_id=shop_id, shop_county=point.county, band=band, fee=band_fee(band, settings)))

    if legs:
        # Chosen by fee, not by nominal distance, so an admin who prices a band
        # out of ladder order still gets the leg they actually charge most for.
        charged = max(legs, key=lambda leg: leg.fee)
        charged_band, base = charged.band, charged.fee
    else:
        charged_band = DistanceBand.unknown_origin
        base = band_fee(DistanceBand.unknown_origin, settings)

    allowance = Decimal(settings.weight_allowance_kg)
    billable_weight = max(Decimal("0"), cart_weight_kg - allowance)
    surcharge = min(
        billable_weight * Decimal(settings.per_kg_fee),
        Decimal(settings.max_weight_surcharge),
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    raw_total = base + surcharge
    floor = Decimal(settings.min_delivery_fee)
    cap = Decimal(settings.max_delivery_fee)

    total = raw_total
    floor_applied = total < floor
    if floor_applied:
        total = floor
    cap_applied = total > cap
    if cap_applied:
        total = cap

    return DeliveryQuote(
        total=_round_up_to_5(total),
        charged_band=charged_band,
        band_fee=base,
        weight_surcharge=surcharge,
        billable_weight_kg=billable_weight,
        legs=tuple(sorted(legs, key=lambda leg: leg.fee, reverse=True)),
        floor_applied=floor_applied,
        cap_applied=cap_applied,
    )


def sum_cart_weight(weights: Iterable[tuple[Optional[str], int]]) -> Decimal:
    """Total known weight for (raw weight_kg, quantity) pairs."""
    return sum((parse_weight_kg(raw) * qty for raw, qty in weights), Decimal("0"))


def point_from_location(obj) -> DeliveryPoint:
    """Adapt a UserAddress or Shop — both carry county + an optional ward — to a
    DeliveryPoint, so the pricing functions stay free of ORM types."""
    if obj is None:
        return DeliveryPoint()
    ward = getattr(obj, "ward", None)
    return DeliveryPoint(
        county=getattr(obj, "county", None),
        subcounty_id=getattr(ward, "subcounty_id", None),
        ward_id=getattr(obj, "ward_id", None),
    )
