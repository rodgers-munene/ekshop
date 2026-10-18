"""Market expansion: the offline Nyeri study overlaid with what Ekshop sells there today.

The study answers "where are the people and the trip generators" for the whole
county; it is a static, committed bundle (see
``backend/scripts/export_market_expansion.py``) because producing it needs the
WorldPop raster and geopandas. This module only reads that bundle and joins it
to live platform data, so the admin page can show demand next to actual
coverage -- the point of the whole tab being that a sublocation full of people
with no shop on Ekshop is today's expansion opportunity, not a footnote.

Two different name sources have to meet in the middle. Shop pins are resolved
to sublocations with the same boundary loader the checkout address picker uses
(``app.services.spatial``), and orders carry the sublocation name they were
placed under in their address snapshot. Both are compared to the study's
polygon names after collapsing whitespace and case, because the GeoJSON is
UPPERCASE with occasional double spaces while the database is proper-case.
"""
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.commerce import OrderGroup, OrderGroupStatus
from app.models.shop import Shop

logger = logging.getLogger(__name__)

BUNDLE_DIR = Path(__file__).resolve().parents[2] / "Data" / "market_expansion"

# A sublocation with at least this many residents and no shop on the platform is
# reported as unserved. It is a single threshold on purpose: the page needs a
# short list of places to go sell to, not a second scoring model.
UNSERVED_POPULATION = 2000

LAYER_FILES = {
    "county": "county.geojson",
    "sublocations": "sublocations.geojson",
    "anchors": "anchors.geojson",
    "suitability": "suitability.geojson",
}

_lock = threading.Lock()
_cache: Optional[dict[str, Any]] = None


def _clean(name: Optional[str]) -> str:
    """Same normalisation the boundary loader applies to admin names."""
    return re.sub(r"\s+", " ", name or "").strip().casefold()


def load_study() -> Optional[dict[str, Any]]:
    """Parse the committed study bundle once per process.

    Returns ``None`` when the bundle is absent so callers can answer with a
    "run the exporter" message instead of a stack trace.
    """
    global _cache
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is not None:
            return _cache
        try:
            layers = {
                key: json.loads((BUNDLE_DIR / filename).read_text(encoding="utf-8"))
                for key, filename in LAYER_FILES.items()
            }
            candidates = json.loads((BUNDLE_DIR / "candidates.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("market expansion bundle missing under %s", BUNDLE_DIR)
            return None
        _cache = {"layers": layers, "candidates": candidates, "summary": _summarise(layers)}
        return _cache


def _summarise(layers: dict[str, Any]) -> dict[str, Any]:
    """Headline numbers for the study, computed once at load."""
    table = _study_sublocations(layers["sublocations"].get("features", []))
    suitability = layers["suitability"].get("features", [])
    scores = [f["properties"].get("suitability") for f in suitability if f.get("properties")]
    county_features = layers["county"].get("features", [])
    county = None
    if county_features:
        county = (county_features[0].get("properties") or {}).get("name")
    return {
        "county": county,
        # The joinable areas, which is what the coverage table has rows for --
        # not the raw polygon count, which is higher.
        "sublocations": len(table),
        "sublocation_polygons": len(layers["sublocations"].get("features", [])),
        "population": sum(entry["population"] for entry in table.values()),
        "scored_cells": len(suitability),
        "suitability_range": [min(scores), max(scores)] if scores else None,
    }


def _walk_coordinates(geometry: dict[str, Any]):
    stack = [geometry.get("coordinates")]
    while stack:
        item = stack.pop()
        if not item:
            continue
        if isinstance(item[0], (int, float)):
            yield item
        else:
            stack.extend(item)


def _bounds(geojson: dict[str, Any]) -> Optional[tuple[float, float, float, float]]:
    """min_lng, min_lat, max_lng, max_lat over every polygon in a collection."""
    lngs: list[float] = []
    lats: list[float] = []
    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        for lng, lat in _walk_coordinates(geometry):
            lngs.append(lng)
            lats.append(lat)
    if not lngs:
        return None
    return min(lngs), min(lats), max(lngs), max(lats)


def _inside(bounds: tuple[float, float, float, float], lat: float, lng: float) -> bool:
    min_lng, min_lat, max_lng, max_lat = bounds
    return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat


def _study_sublocations(features: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Study polygons keyed by normalised name, carrying their demand numbers.

    The table is keyed by name because that is the only handle live data has on
    a place: an order snapshot and a reverse geocode both yield a name, not a
    polygon. A handful of Nyeri names cover two polygons ("MUNYU" appears in two
    locations), and those are folded into one row with their populations and
    areas added together, so the row still describes everyone the name refers
    to. `polygons` records how many made it up.
    """
    table: dict[str, dict[str, Any]] = {}
    for feature in features:
        props = feature.get("properties") or {}
        name = props.get("name")
        key = _clean(name)
        population = props.get("population") or 0
        area = props.get("area_km2") or 0.0
        entry = table.get(key)
        if entry is None:
            table[key] = {
                "name": name or "Unnamed area",
                "population": population,
                "density": props.get("density"),
                "area_km2": area,
                "polygons": 1,
            }
            continue
        entry["polygons"] += 1
        entry["population"] += population
        entry["area_km2"] = round(entry["area_km2"] + area, 3)
        if entry["area_km2"]:
            entry["density"] = round(entry["population"] / entry["area_km2"], 1)
    return table


def _shop_counts_by_sublocation(
    db: Session, bounds: Optional[tuple[float, float, float, float]]
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Pin shops to sublocations using the boundary loader, once per pin.

    Only pins inside the study's bounding box are resolved: the boundary loader
    has to test each point against every polygon in the country, so there is no
    reason to spend that on shops in another county.
    """
    shops = (
        db.query(Shop)
        .filter(Shop.lat.isnot(None), Shop.lng.isnot(None))
        .all()
    )
    counts: dict[str, int] = {}
    listed: list[dict[str, Any]] = []
    for shop in shops:
        if bounds is not None and not _inside(bounds, float(shop.lat), float(shop.lng)):
            continue
        listed.append(
            {
                "id": str(shop.id),
                "name": shop.name,
                "county": shop.county,
                "town": shop.town,
                "lat": float(shop.lat),
                "lng": float(shop.lng),
                "status": shop.status.value if hasattr(shop.status, "value") else str(shop.status),
                "is_verified": bool(shop.is_verified),
            }
        )
        resolved = _resolve_sublocation(float(shop.lat), float(shop.lng))
        if resolved:
            key = _clean(resolved)
            counts[key] = counts.get(key, 0) + 1
    return counts, listed


def _resolve_sublocation(lat: float, lng: float) -> Optional[str]:
    """Import the boundary loader lazily: it reads ~35 MB of polygons on first use."""
    from app.services import spatial

    try:
        hit = spatial.reverse_geocode(lat, lng)
    except Exception:  # pragma: no cover - a missing bundle must not break the page
        logger.exception("reverse geocode failed for %s,%s", lat, lng)
        return None
    return (hit or {}).get("sublocation")


def _order_counts_by_sublocation(db: Session) -> dict[str, int]:
    """Paid orders per sublocation, read from the address snapshot.

    The snapshot kept the name the buyer checked out under, so this needs no
    geometry at all -- and it stays correct for orders placed before any
    boundary file changed.
    """
    rows = (
        db.query(
            OrderGroup.delivery_address["sublocation"].astext.label("sublocation"),
            func.count(OrderGroup.id),
        )
        .filter(OrderGroup.status == OrderGroupStatus.paid)
        .group_by(OrderGroup.delivery_address["sublocation"].astext)
        .all()
    )
    counts: dict[str, int] = {}
    for name, count in rows:
        if name:
            counts[_clean(name)] = int(count)
    return counts


def build_coverage(db: Session, study: dict[str, Any]) -> dict[str, Any]:
    """Live Ekshop coverage for the study area."""
    bounds = _bounds(study["layers"]["county"])
    sublocations = _study_sublocations(study["layers"]["sublocations"].get("features", []))
    shop_counts, shops = _shop_counts_by_sublocation(db, bounds)
    order_counts = _order_counts_by_sublocation(db)

    rows = []
    for key, info in sublocations.items():
        shops_here = shop_counts.get(key, 0)
        orders_here = order_counts.get(key, 0)
        population = info["population"] or 0
        rows.append(
            {
                **info,
                "shops": shops_here,
                "orders": orders_here,
                "unserved": shops_here == 0 and population >= UNSERVED_POPULATION,
            }
        )
    rows.sort(key=lambda row: (row["population"] or 0), reverse=True)

    # Orders whose sublocation no longer matches a study polygon (renamed or
    # outside Nyeri) are kept in the headline total but not attributed.
    attributed = sum(row["orders"] for row in rows)
    total_orders = sum(order_counts.values())
    if total_orders != attributed:
        logger.info(
            "market expansion: %d of %d paid orders fall outside a study sublocation",
            total_orders - attributed,
            total_orders,
        )

    return {
        "shops": shops,
        "sublocations": rows,
        "summary": {
            "shops_pinned": len(shops),
            "shops_active": sum(1 for s in shops if s["status"] == "active"),
            "paid_orders": total_orders,
            "paid_orders_attributed": attributed,
            "unserved_sublocations": sum(1 for row in rows if row["unserved"]),
            "unserved_population": sum(row["population"] for row in rows if row["unserved"]),
            "anchor_count": len(study["layers"]["anchors"].get("features", [])),
        },
    }


def build_report(db: Session) -> Optional[dict[str, Any]]:
    """Everything the Market Expansion page draws, in one response.

    The static layers ride along rather than living in the frontend's public
    directory so that the study data is versioned next to the other boundary
    files it is derived from, and so the page has a single request to make.

    The two halves are deliberately not all-or-nothing. The study is a committed
    bundle that needs no database at all; coverage is a live join against
    whichever database the deployment happens to point at. If that join fails --
    a schema that has drifted behind the models, a connection that is down --
    the analysis must still be delivered, so the failure is reported in the
    payload instead of taking the whole request with it. A blank tab would say
    the study is missing when it is not.
    """
    study = load_study()
    if study is None:
        return None
    report: dict[str, Any] = {
        "study": {
            "source": study["candidates"].get("source"),
            "weights": study["candidates"].get("weights"),
            **study["summary"],
            "anchors": len(study["layers"]["anchors"].get("features", [])),
        },
        "layers": study["layers"],
        "candidates": study["candidates"].get("sites", []),
        "coverage": None,
        "coverage_error": None,
    }
    try:
        report["coverage"] = build_coverage(db, study)
    except Exception:
        logger.exception("market expansion: live coverage unavailable")
        report["coverage_error"] = (
            "Live coverage could not be read from the platform database, so "
            "shop counts and paid orders are not shown. The study above is "
            "complete and unaffected."
        )
    return report
