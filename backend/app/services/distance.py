"""Road distance and travel time, as the technical specification requires.

§3.2: *"Distances must use road distance, not straight-line/geodesic distance."*

This is not a stylistic preference. In built-up areas road distance is routinely
20-40% longer than straight-line, so a geodesic quote **systematically
undercharges**, and the error grows with distance. The previous code used the
Haversine great-circle formula for pricing; this module exists to make that
impossible to do by accident.

Two rules govern everything here:

1. **Straight-line is never silently used for a price.** :class:`RoadDistance`
   carries ``source`` and ``approximate``. A caller that wants a firm price must
   check ``approximate``; a fallback that forgets is visible rather than invisible.

2. **Straight-line is still legitimate elsewhere.** Radius scans ("is this rider
   within 5 km?") and GPS fraud detection ("is this movement physically
   possible?") both want a cheap, monotonic approximation and must not pay for a
   routing call. :class:`StraightLineProvider` exists for those callers and is
   documented as unsuitable for pricing.

OSRM is the default. It is self-hosted, has no per-request cost, and returns both
distance and duration, which the SLA and batching rules need.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6_371_000.0


class DistanceSource(str, Enum):
    """Where a distance came from. Persisted with the calculation."""

    osrm = "osrm"
    straight_line = "straight_line"
    cache = "cache"


class DistanceError(RuntimeError):
    """Distance could not be established and no fallback was permitted."""


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat <= 90.0:
            raise ValueError(f"lat out of range: {self.lat}")
        if not -180.0 <= self.lng <= 180.0:
            raise ValueError(f"lng out of range: {self.lng}")

    def rounded(self, precision: int) -> tuple[float, float]:
        return (round(self.lat, precision), round(self.lng, precision))


@dataclass(frozen=True)
class RoadDistance:
    """A distance result that always says how it was obtained.

    `approximate=True` means "not a real road distance". Anything that turns a
    distance into a customer-facing price must refuse to proceed on an
    approximate value, or must record that it did.
    """

    metres: float
    duration_seconds: Optional[float]
    source: DistanceSource
    approximate: bool

    @property
    def km(self) -> float:
        return round(self.metres / 1000.0, 4)


class DistanceProvider(Protocol):
    name: str

    def road_distance(self, origin: GeoPoint, destination: GeoPoint) -> RoadDistance:
        ...


def haversine_metres(a: GeoPoint, b: GeoPoint) -> float:
    """Great-circle distance. NOT valid for pricing -- see the module docstring."""
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlambda = math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


class StraightLineProvider:
    """Haversine, always flagged approximate.

    Intended for radius scans and fraud detection, where a cheap monotonic
    approximation is correct and a routing call would be wasteful. Do not use it
    to price a delivery.
    """

    name = "straight_line"

    def road_distance(self, origin: GeoPoint, destination: GeoPoint) -> RoadDistance:
        return RoadDistance(
            metres=haversine_metres(origin, destination),
            duration_seconds=None,
            source=DistanceSource.straight_line,
            approximate=True,
        )


class OSRMProvider:
    """Road distance and duration from a self-hosted OSRM instance.

    OSRM's `/route/v1/driving` service returns the distance along the road
    network for the fastest route, plus an estimated duration. Coordinates go in
    as `longitude,latitude` -- the reverse of everywhere else in this codebase,
    which is the single most common way to get an OSRM integration wrong.
    """

    name = "osrm"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.timeout = timeout_seconds if timeout_seconds is not None else settings.OSRM_TIMEOUT_SECONDS
        # A client is injected in tests; in production one is built per provider
        # instance and reused so connections are pooled.
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
            self._client = None

    @staticmethod
    def _coordinate(point: GeoPoint) -> str:
        return f"{point.lng},{point.lat}"

    def road_distance(self, origin: GeoPoint, destination: GeoPoint) -> RoadDistance:
        coordinates = f"{self._coordinate(origin)};{self._coordinate(destination)}"
        url = f"{self.base_url}/route/v1/driving/{coordinates}"
        try:
            response = self._get_client().get(
                url,
                params={"overview": "false", "alternatives": "false", "steps": "false"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DistanceError(f"OSRM road distance unavailable: {exc}") from exc

        if payload.get("code") != "Ok":
            raise DistanceError(f"OSRM returned {payload.get('code')!r}: {payload.get('message')}")

        routes = payload.get("routes") or []
        if not routes:
            raise DistanceError("OSRM returned no route")

        route = routes[0]
        return RoadDistance(
            metres=float(route["distance"]),
            duration_seconds=(
                float(route["duration"]) if route.get("duration") is not None else None
            ),
            source=DistanceSource.osrm,
            # A successful OSRM call is a real road distance, not an estimate of
            # one. The duration is OSRM's free-flow estimate, but the distance is
            # measured from the road network.
            approximate=False,
        )


class _TTLCache:
    """Small thread-safe TTL cache.

    Road distance between two fixed coordinates does not change, so this cache
    is close to free and removes a network call from almost every quote. Bounded
    so a long-running process cannot grow without limit.
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._entries: dict[tuple, tuple[float, RoadDistance]] = {}
        self._lock = threading.Lock()
        self._max_entries = max_entries

    def get(self, key: tuple) -> Optional[RoadDistance]:
        with self._lock:
            hit = self._entries.get(key)
            if hit is None:
                return None
            expires_at, value = hit
            if expires_at < time.monotonic():
                del self._entries[key]
                return None
            return value

    def put(self, key: tuple, value: RoadDistance, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            if len(self._entries) >= self._max_entries:
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                del self._entries[oldest]
            self._entries[key] = (time.monotonic() + ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_cache = _TTLCache()


def get_provider(name: Optional[str] = None) -> DistanceProvider:
    """Build the configured provider.

    ``straight_line`` is selectable but logs a warning on every construction,
    because choosing it for pricing is the mistake this module exists to prevent.
    """
    chosen = (name or settings.DISTANCE_PROVIDER or "osrm").strip().lower()
    if chosen in ("osrm", "road", "osrm_self_hosted"):
        return OSRMProvider()
    if chosen in ("straight_line", "haversine", "geodesic"):
        logger.warning(
            "DISTANCE_PROVIDER is '%s'. Straight-line distance is not valid for "
            "pricing (spec3.2) and will undercharge by roughly 20-40%%. Use it "
            "only for radius scans and fraud detection.",
            chosen,
        )
        return StraightLineProvider()
    raise DistanceError(
        f"Unknown DISTANCE_PROVIDER {chosen!r}; expected 'osrm' or 'straight_line'"
    )


def get_road_distance(
    origin: GeoPoint,
    destination: GeoPoint,
    provider: Optional[DistanceProvider] = None,
) -> RoadDistance:
    """Road distance between two points, cached, with a flagged fallback.

    On provider failure this returns a straight-line result marked
    ``approximate=True`` rather than raising, because refusing to quote at all is
    worse for a customer than quoting an honestly-flagged estimate. A caller that
    needs a firm price must check ``approximate``; :func:`require_firm_distance`
    does that for the pricing path.
    """
    provider = provider or get_provider()
    if origin.rounded(settings.DISTANCE_COORD_PRECISION) == destination.rounded(
        settings.DISTANCE_COORD_PRECISION
    ):
        return RoadDistance(0.0, 0.0, DistanceSource.osrm, False)

    key = (
        provider.name,
        *origin.rounded(settings.DISTANCE_COORD_PRECISION),
        *destination.rounded(settings.DISTANCE_COORD_PRECISION),
    )
    cached = _cache.get(key)
    if cached is not None:
        return RoadDistance(
            metres=cached.metres,
            duration_seconds=cached.duration_seconds,
            source=DistanceSource.cache,
            approximate=cached.approximate,
        )

    try:
        result = provider.road_distance(origin, destination)
    except DistanceError:
        if not settings.DISTANCE_ALLOW_STRAIGHT_LINE_FALLBACK:
            raise
        logger.warning(
            "Road distance unavailable; falling back to a flagged straight-line "
            "estimate. This undercharges and must not be shown as a firm price.",
            exc_info=True,
        )
        result = StraightLineProvider().road_distance(origin, destination)

    _cache.put(key, result, settings.DISTANCE_CACHE_TTL_SECONDS)
    return result


def require_firm_distance(result: RoadDistance) -> RoadDistance:
    """Guard for the pricing path: refuse an approximate distance.

   3.2 forbids pricing on straight-line distance. Rather than trusting every
    call site to remember, the pricing engine calls this and gets an explicit
    failure instead of a quietly wrong price.
    """
    if result.approximate:
        raise DistanceError(
            "Refusing to price from an approximate distance "
            f"(source={result.source.value}). The road-distance provider is "
            "unavailable or DISTANCE_PROVIDER is set to straight_line."
        )
    return result


def clear_cache() -> None:
    """Test hook."""
    _cache.clear()