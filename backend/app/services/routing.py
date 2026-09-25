import logging

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


async def get_route_matrix(coords: list[tuple[float, float]]) -> list[list[dict]] | None:
    """Driving distance and time between every pair of points, via the ORS matrix API.

    coords: list of (lat, lng)
    Returns an N x N matrix where [i][j] is {distance_km, duration_min} from i
    to j, or None when ORS isn't configured or the request fails, so callers
    can fall back to straight-line distances.
    """
    if not settings.ORS_API_KEY or len(coords) < 2:
        return None

    body = {
        "locations": [[lng, lat] for lat, lng in coords],
        "metrics": ["distance", "duration"],
    }
    headers = {"Authorization": settings.ORS_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(ORS_MATRIX_URL, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        distances = data["distances"]
        durations = data["durations"]
        return [
            [
                {
                    "distance_km": distances[i][j] / 1000 if distances[i][j] is not None else None,
                    "duration_min": durations[i][j] / 60 if durations[i][j] is not None else None,
                }
                for j in range(len(coords))
            ]
            for i in range(len(coords))
        ]
    except Exception as exc:
        logger.warning("ORS matrix request failed: %s", exc)
        return None
