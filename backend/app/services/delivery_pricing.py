from decimal import Decimal
from typing import Optional

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
    # North Eastern
    "Garissa": "North Eastern",
    "Wajir": "North Eastern",
    "Mandera": "North Eastern",
}


def get_region(county: Optional[str]) -> Optional[str]:
    if not county:
        return None
    return COUNTY_REGIONS.get(county.strip())


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
