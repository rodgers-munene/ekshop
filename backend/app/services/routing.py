import logging
from decimal import Decimal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ORS_DIRECTIONS_URL = f"{settings.ORS_BASE_URL}/ors/v2/directions/driving-car"
ORS_MATRIX_URL = f"{settings.ORS_BASE_URL}/ors/v2/matrix/driving-car"


async def get_route_eta_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> dict:
    """Call ORS directions API and return distance_km + duration_min."""
    if not settings.ORS_API_KEY:
        return {"distance_km": None, "duration_min": None}

    params = {
        "start": f"{lng1},{lat1}",
        "end": f"{lng2},{lat2}",
        "overview": "false",
    }
    headers = {"Authorization": settings.ORS_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(ORS_DIRECTIONS_URL, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("ORS directions request failed: %s", exc)
        return {"distance_km": None, "duration_min": None}

    try:
        route = data["routes"][0]
        distance_m = route["summary"]["distance"]
        duration_s = route["summary"]["duration"]
        return {
            "distance_km": round(distance_m / 1000, 2),
            "duration_min": round(duration_s / 60, 0),
        }
    except Exception as exc:
        logger.warning("ORS response parsing failed: %s", exc)
        return {"distance_km": None, "duration_min": None}


async def get_route_matrix(coords: list[tuple[float, float]]) -> list[dict]:
    """Call ORS matrix API for multiple origins/destinations.

    coords: list of (lat, lng)
    Returns list of {distance_km, duration_min} per pair.
    """
    if not settings.ORS_API_KEY or len(coords) < 2:
        return [{"distance_km": None, "duration_min": None}] * len(coords)

    body = {
        "coordinates": [[lng, lat] for lat, lng in coords],
        "metrics": ["distance", "duration"],
    }
    headers = {"Authorization": settings.ORS_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(ORS_MATRIX_URL, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("ORS matrix request failed: %s", exc)
        return [{"distance_km": None, "duration_min": None}] * len(coords)

    distances = data.get("distances", [])
    durations = data.get("durations", [])
    results = []
    for i in range(len(coords)):
        d_m = distances[i] if i < len(distances) else None
        d_s = durations[i] if i < len(durations) else None
        results.append(
            {
                "distance_km": round(d_m / 1000, 2) if d_m is not None else None,
                "duration_min": round(d_s / 60, 0) if d_s is not None else None,
            }
        )
    return results
