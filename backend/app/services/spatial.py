"""Reverse-geocode and location search over the bundled Kenya geojson.

The ward polygons in ``backend/Data/geojson/kenya_wards.geojson`` resolve a
(lat, lng) to county / subcounty / ward.  ``kenya_locations.geojson`` and
``kenya_sublocations.geojson`` add the finer location / sublocation levels that
buyers usually cannot name on their own (the point of the "spatially
intelligent" positioning tool).  Boundaries are loaded lazily and cached in
memory via :func:`_layers`, so point-in-polygon lookups stay fast.

Coordinate order everywhere is GeoJSON's (lng, lat).
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Optional

from shapely.geometry import Point, shape
from shapely.prepared import prep

DATA_DIR = Path(__file__).resolve().parents[2] / "Data" / "geojson"

# Rough Kenya extent; reject nonsense coordinates before scanning polygons.
KENYA_BOUNDS = {"min_lng": 33.5, "max_lng": 41.9, "min_lat": -5.1, "max_lat": 5.6}

_lock = threading.Lock()
_layers_cache: Optional[dict[str, list[dict[str, Any]]]] = None


def _clean(value: str) -> str:
    """Normalize admin names: collapse whitespace, casefold.

    GeoJSON names are UPPERCASE with occasional double spaces (e.g.
    "Runyenjes  Sub County") while the DB names are proper-case with single
    spaces, so naive string matching misses.
    """
    return re.sub(r"\s+", " ", value or "").casefold()


def _as_code(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _build_entries(filename: str, props_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    path = DATA_DIR / filename
    entries = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    for feature in data.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        props = {
            key: (feature.get("properties") or {}).get(key)
            for key in props_fields
        }
        try:
            shapely_geom = shape(geometry)
        except (ValueError, NotImplementedError):
            continue
        entry = {
            "props": props,
            "prepared": prep(shapely_geom),
            "bounds": shapely_geom.bounds,
            "centroid": shapely_geom.centroid,
        }
        entries.append(entry)
    return entries


def _layers() -> dict[str, list[dict[str, Any]]]:
    """Load each boundary layer once, guarded by a module-level lock."""
    global _layers_cache
    if _layers_cache is not None:
        return _layers_cache
    with _lock:
        if _layers_cache is not None:
            return _layers_cache
        _layers_cache = {
            "wards": _build_entries("kenya_wards.geojson", ("county", "subcounty", "ward", "ward_code")),
            "locations": _build_entries("kenya_locations.geojson", ("location", "location_code")),
            "sublocations": _build_entries("kenya_sublocations.geojson", ("sublocation", "sublocation_code", "location_code")),
        }
        return _layers_cache


def _contains(entries: list[dict[str, Any]], point: Point) -> Optional[dict[str, Any]]:
    for entry in entries:
        minx, miny, maxx, maxy = entry["bounds"]
        if point.x < minx or point.x > maxx or point.y < miny or point.y > maxy:
            continue
        if entry["prepared"].intersects(point):
            return entry
    return None


def _centroid_lnglat(entry: dict[str, Any]) -> Optional[tuple[float, float]]:
    centroid = entry.get("centroid")
    if centroid is None or centroid.is_empty:
        return None
    return (float(centroid.x), float(centroid.y))


def _location_entry_for_code(code: Optional[int]) -> Optional[dict[str, Any]]:
    if code is None:
        return None
    for entry in _layers()["locations"]:
        if _as_code(entry["props"].get("location_code")) == code:
            return entry
    return None


def _search_index() -> list[dict[str, Any]]:
    """Flatten all layers into a name-searchable index with centroids."""
    output: list[dict[str, Any]] = []
    for entry in _layers()["wards"]:
        centroid = _centroid_lnglat(entry)
        if centroid is None:
            continue
        output.append({
            "type": "ward",
            "name": entry["props"].get("ward") or "",
            "county": entry["props"].get("county"),
            "subcounty": entry["props"].get("subcounty"),
            "ward": entry["props"].get("ward"),
            "lat": centroid[1],
            "lng": centroid[0],
        })

    ward_by_code = {}
    for entry in _layers()["wards"]:
        code = _as_code(entry["props"].get("ward_code"))
        if code is not None:
            ward_by_code[code] = entry

    for layername, filename, fields in (
        ("location", "locations", ("location", "location_code")),
        ("sublocation", "sublocations", ("sublocation", "location_code")),
    ):
        for entry in _layers()[layername + "s"]:
            centroid = _centroid_lnglat(entry)
            if centroid is None:
                continue
            name = entry["props"].get(fields[0]) or ""
            code = _as_code(entry["props"].get(fields[1]))
            ward_code = (code or 0) // 10 if code else None
            ward_entry = ward_by_code.get(ward_code) if ward_code else None
            output.append({
                "type": layername,
                "name": name,
                "county": ward_entry["props"].get("county") if ward_entry else None,
                "subcounty": ward_entry["props"].get("subcounty") if ward_entry else None,
                "ward": ward_entry["props"].get("ward") if ward_entry else None,
                "lat": centroid[1],
                "lng": centroid[0],
            })
    return output


_search_index_cache: Optional[list[dict[str, Any]]] = None


def search(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Case-insensitive name search across ward, location and sublocation."""
    global _search_index_cache
    q = _clean(query)
    if not q:
        return []
    with _lock:
        if _search_index_cache is None:
            _search_index_cache = _search_index()
    results = []
    for entry in _search_index_cache:
        haystack = " ".join(filter(None, (entry[k] for k in ("name", "subcounty", "county", "ward"))))
        if q in _clean(haystack):
            parts = [entry.get("name")]
            for key in ("subcounty", "county"):
                if entry.get(key):
                    parts.append(entry[key])
            subtitle = ", ".join(parts)
            results.append({**entry, "subtitle": subtitle})
            if len(results) >= limit:
                break
    return results


def reverse_geocode(lat: float, lng: float) -> Optional[dict[str, Any]]:
    """Resolve a (lat, lng) to the county/subcounty/ward/location/sublocation chain.

    Returns None when the point is outside Kenya or falls in none of the
    boundaries.  The caller is expected to nudge by a few meters and retry when
    a point lands right on a shared border.
    """
    if not (KENYA_BOUNDS["min_lng"] <= lng <= KENYA_BOUNDS["max_lng"]):
        return None
    if not (KENYA_BOUNDS["min_lat"] <= lat <= KENYA_BOUNDS["max_lat"]):
        return None

    point = Point(lng, lat)
    layers = _layers()

    ward = _contains(layers["wards"], point)
    if ward is None:
        return None

    result: dict[str, Any] = {
        "lat": lat,
        "lng": lng,
        "county": ward["props"].get("county"),
        "subcounty": ward["props"].get("subcounty"),
        "ward": ward["props"].get("ward"),
        "ward_code": _as_code(ward["props"].get("ward_code")),
        "location": None,
        "sublocation": None,
    }

    location = _contains(layers["locations"], point)
    sublocation = _contains(layers["sublocations"], point)

    if location is not None:
        result["location"] = location["props"].get("location")
        result["location_code"] = _as_code(location["props"].get("location_code"))
    if sublocation is not None:
        result["sublocation"] = sublocation["props"].get("sublocation")
        result["location_code"] = _as_code(sublocation["props"].get("location_code"))

    if result["location"] is None:
        location_entry = _location_entry_for_code(result.get("location_code"))
        if location_entry is not None:
            result["location"] = location_entry["props"].get("location")

    return result