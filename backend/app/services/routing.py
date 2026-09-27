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


async def get_route_matrix(coords: list[tuple[float, float]]) -> list[list[dict]]:
    """Call ORS matrix API for multiple origins/destinations.

    coords: list of (lat, lng)
    Returns a 2D matrix where matrix[i][j] is {distance_km, duration_min}.
    """
    n = len(coords)
    empty = {"distance_km": None, "duration_min": None}
    if not settings.ORS_API_KEY or n < 2:
        return [[dict(empty) for _ in range(n)] for _ in range(n)]

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
        return [[dict(empty) for _ in range(n)] for _ in range(n)]

    distances = data.get("distances") or []
    durations = data.get("durations") or []

    def cell(row: int, col: int) -> dict:
        d_m = distances[row][col] if row < len(distances) and col < len(distances[row]) else None
        d_s = durations[row][col] if row < len(durations) and col < len(durations[row]) else None
        if d_m is None:
            return dict(empty)
        return {
            "distance_km": round(d_m / 1000, 2),
            "duration_min": round(d_s / 60, 0) if d_s is not None else None,
        }

    return [[cell(i, j) for j in range(n)] for i in range(n)]
