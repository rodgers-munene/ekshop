import logging
import math
from typing import List, Tuple, Optional, Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ORS_DIRECTIONS_URL = f"{settings.ORS_BASE_URL}/ors/v2/directions/driving-car"
ORS_MATRIX_URL = f"{settings.ORS_BASE_URL}/ors/v2/matrix/driving-car"


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate haversine distance between two points in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def two_opt(route: List[int], matrix: List[List[Dict[str, Any]]]) -> List[int]:
    """2-opt local search improvement for TSP.
    
    Args:
        route: Current route as list of node indices
        matrix: Distance/duration matrix
        
    Returns:
        Improved route
    """
    n = len(route)
    if n < 4:
        return route
    
    def route_distance(route: List[int]) -> float:
        total = 0.0
        for i in range(len(route) - 1):
            leg = matrix[route[i]][route[i + 1]]
            if isinstance(leg, dict):
                dist = leg.get("distance_km")
                if dist is not None:
                    total += dist
                else:
                    # Fallback - should not happen with proper matrix
                    total += 1.0
            else:
                total += float(leg)
        return total
    
    best_route = route[:]
    best_distance = route_distance(best_route)
    improved = True
    
    while improved:
        improved = False
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                # Try reversing segment between i and j
                new_route = best_route[:i] + best_route[i:j+1][::-1] + best_route[j+1:]
                new_distance = route_distance(new_route)
                if new_distance < best_distance - 0.001:  # Small epsilon
                    best_route = new_route
                    best_distance = new_distance
                    improved = True
                    break
            if improved:
                break
    
    return best_route


def route_distance(route: List[int], matrix: List[List[Dict[str, Any]]], distance_only: bool = True) -> float:
    """Calculate total distance of a route."""
    total = 0.0
    for i in range(len(route) - 1):
        leg = matrix[route[i]][route[i + 1]]
        if isinstance(leg, dict):
            dist = leg.get("distance_km")
            if dist is not None:
                total += dist
            else:
                total += 1.0  # fallback
        else:
            total += float(leg)
    return total


def nearest_neighbor_route(matrix: List[List[Dict[str, Any]]], start: int = 0) -> List[int]:
    """Simple nearest neighbor heuristic for TSP."""
    n = len(matrix)
    if n <= 1:
        return list(range(n))
    
    unvisited = set(range(n))
    unvisited.discard(start)
    path = [start]
    current = start
    
    while unvisited:
        next_node = min(unvisited, key=lambda j: _get_distance(matrix, current, j))
        path.append(next_node)
        unvisited.remove(next_node)
        current = next_node
    
    return path


def _get_distance(matrix: List[List[Dict[str, Any]]], i: int, j: int) -> float:
    leg = matrix[i][j]
    if isinstance(leg, dict):
        dist = leg.get("distance_km")
        if dist is not None:
            return dist
    return float(leg) if leg else 1.0


def optimize_route_2opt(
    coords: List[Tuple[float, float]],
    matrix: List[List[Dict[str, Any]]],
    start_idx: int = 0,
    max_iterations: int = 1000,
) -> Tuple[List[int], float, Optional[float]]:
    """Optimize route using nearest neighbor + 2-opt improvement.
    
    Returns:
        (optimized_path, total_distance_km, total_duration_min)
    """
    n = len(coords)
    if n <= 1:
        return [0], 0.0, None
    if n == 2:
        leg = matrix[0][1]
        if isinstance(leg, dict):
            return [0, 1], leg.get("distance_km", 0.0), leg.get("duration_min")
        return [0, 1], float(leg), None
    
    # Initial route with nearest neighbor
    route = nearest_neighbor_route(matrix)
    
    # Ensure start_idx is at position 0
    if route[0] != 0:
        idx = route.index(0)
        route = route[idx:] + route[:idx]
    
    # 2-opt improvement
    improved_route = two_opt(route, matrix)
    
    # Calculate total distance and duration
    total_dist = 0.0
    total_dur = 0.0
    for i in range(len(improved_route) - 1):
        leg = matrix[improved_route[i]][improved_route[i + 1]]
        if isinstance(leg, dict):
            total_dist += leg.get("distance_km", 0.0)
            if leg.get("duration_min") is not None:
                total_dur += leg["duration_min"]
    
    return improved_route, round(total_dist, 2), round(total_dur, 2) if total_dur > 0 else None


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
