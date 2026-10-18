"""Turning a shopper's coordinates into something a query can use.

Every proximity filter and ranking goes through here, so the formula, the earth
radius and the rules around missing coordinates are stated once:

* A shop with no coordinates cannot be claimed to be near anyone. It is left out
  of a radius filter and carries no distance -- it is never treated as "0 km
  away". During rollout most shops will not have a pin yet, which is exactly why
  that rule has to be explicit rather than accidental.
* A missing buyer pin is not an error. Callers fall back to the county-level
  behaviour that existed before, which is why the ranking helper below returns a
  neutral weight instead of raising.

The SQL formula is the haversine great-circle distance. That is legitimate here
and only here: `app/services/distance.py` forbids straight-line distance for
*pricing*, and names radius scans as the case it is for -- a road distance per
product would need a routing call each and buys nothing for a "near me" sort.
"""
from math import cos, radians
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.sql.elements import ColumnElement

from app.models.shop import Shop
from app.services.distance import EARTH_RADIUS_M, GeoPoint, haversine_metres

# Derived, not restated: the distance module already owns the earth radius, and a
# second copy of that number is how a SQL distance and a Python distance quietly
# stop agreeing with each other.
EARTH_RADIUS_KM = EARTH_RADIUS_M / 1000.0
KM_PER_DEGREE_LAT = 111.32


def distance_km_expr(lat: float, lng: float) -> ColumnElement:
    """SQL for the great-circle distance in km from (lat, lng) to the shop."""
    half_dlat = func.radians(Shop.lat - lat) / 2
    half_dlng = func.radians(Shop.lng - lng) / 2
    h = (
        func.power(func.sin(half_dlat), 2)
        + func.cos(func.radians(lat)) * func.cos(func.radians(Shop.lat)) * func.power(func.sin(half_dlng), 2)
    )
    # least(1, ...) guards the asin domain against floating-point overshoot.
    return 2 * EARTH_RADIUS_KM * func.asin(func.least(1.0, func.sqrt(h)))


def within_radius(lat: float, lng: float, radius_km: float) -> ColumnElement:
    """Boolean SQL: this shop has coordinates and lies within ``radius_km``.

    The bounding box is a cheap prefilter and the only part an index on
    ``shops(lat, lng)`` can use; the haversine term is what decides, because a box
    is not a circle. Shops without coordinates are excluded: we cannot say they are
    near the shopper, so we do not claim it.
    """
    lat_delta = radius_km / KM_PER_DEGREE_LAT
    lng_delta = radius_km / (KM_PER_DEGREE_LAT * max(cos(radians(lat)), 0.01))
    return and_(
        Shop.lat.is_not(None),
        Shop.lng.is_not(None),
        Shop.lat.between(lat - lat_delta, lat + lat_delta),
        Shop.lng.between(lng - lng_delta, lng + lng_delta),
        distance_km_expr(lat, lng) <= radius_km,
    )


def distance_km(
    origin_lat: float,
    origin_lng: float,
    dest_lat: Optional[float],
    dest_lng: Optional[float],
) -> Optional[float]:
    """Python-side distance for a handful of already-fetched rows.

    Same formula as :func:`distance_km_expr`, so a distance shown next to a result
    agrees with the distance that ranked it.
    """
    if dest_lat is None or dest_lng is None:
        return None
    metres = haversine_metres(
        GeoPoint(float(origin_lat), float(origin_lng)),
        GeoPoint(float(dest_lat), float(dest_lng)),
    )
    return round(metres / 1000.0, 1)


def proximity_weight(away_km: Optional[float], radius_km: float) -> float:
    """Ranking multiplier for a product whose shop is this far away.

    A boost, never a filter: far products sink, they do not disappear. Bands are
    deliberately coarse -- pickup and same-day delivery are the real reasons
    nearness matters, and those turn on a handful of kilometres, not on metres.
    An unknown distance is neutral, never "nearest".
    """
    if away_km is None:
        return 1.0
    if away_km <= 2:
        return 5.0
    if away_km <= 5:
        return 3.5
    if away_km <= radius_km:
        return 2.0
    return 1.0
