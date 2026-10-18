"""Trim the offline Nyeri market-suitability study into the bundle the admin
Market Expansion tab serves.

The study itself runs outside this repo and needs geopandas, rasterio and the
WorldPop raster -- none of which the API runtime has, and none of which the
dashboard needs once the numbers exist. So the study stays where it is and this
script copies only its output, shaped for the page: the county outline, the
sublocation demand polygons, the demand anchors, the scored grid and the
candidate store sites. The result is committed, because the tab has to render on
a machine that has never seen the study folder.

It is a reshaping pass, not a recomputation: every population, density and score
is the study's own number. It rounds coordinates to ~11 m (4 decimal places),
drops the properties the page does not read and the redundant `crs` block, which
takes the bundle from ~4 MB to a few hundred KB. The one thing it adds is a name
for the single sublocation polygon the source ships unnamed, taken from the
platform's own boundary loader -- see `fill_missing_names`.

    python backend/scripts/export_market_expansion.py
    python backend/scripts/export_market_expansion.py --source <processed dir>

Default source is the sibling checkout of the study, ../nyeri_suitability, since
the study lives next to this repo rather than in it.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
DEFAULT_SOURCE = REPO.parent / "nyeri_suitability" / "data" / "processed"
DEFAULT_OUT = BACKEND / "Data" / "market_expansion"

# The study scores every 1 km cell 0-100. Below this the cell is ordinary
# farmland: drawing it would bury the places the map exists to point at.
SUITABILITY_FLOOR = 55


def load(source: Path, name: str) -> Optional[dict]:
    path = source / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def representative_point(feature: dict) -> tuple[float, float]:
    """Centroid of a polygon's outer ring, good enough for a name lookup."""
    geometry = feature["geometry"]
    ring = geometry["coordinates"][0]
    if geometry["type"] == "MultiPolygon":
        ring = geometry["coordinates"][0][0]
    lng = sum(point[0] for point in ring) / len(ring)
    lat = sum(point[1] for point in ring) / len(ring)
    return lat, lng


def fill_missing_names(features: list[dict]) -> int:
    """Label the sublocation polygons that arrive without a name.

    One polygon in the source has an empty `SLNAME` -- the platform's own
    boundary loader returns a blank sublocation for it too, so it is a defect in
    the KNBS file rather than in the study. Left alone it draws as an
    anonymous shaded area with no row in the coverage table, which is exactly
    where an expansion decision should not be made blind. The parent location
    (also from the platform's boundary loader) is the most specific name the
    data still carries, so that is what the area is called.
    """
    blank = [f for f in features if not (f["properties"].get("name") or "").strip()]
    if not blank:
        return 0
    sys.path.insert(0, str(BACKEND))
    from app.services import spatial

    for feature in blank:
        lat, lng = representative_point(feature)
        hit = spatial.reverse_geocode(lat, lng) or {}
        label = hit.get("location") or hit.get("ward") or f"{lat:.3f}, {lng:.3f}"
        feature["properties"]["name"] = label
        feature["properties"]["name_from"] = "location"
        print(f"  unnamed polygon at {lat:.4f},{lng:.4f} -> {label}")
    return len(blank)


def round_coords(value: Any) -> Any:
    """Recursively round every coordinate in a GeoJSON geometry."""
    if isinstance(value, (int, float)):
        return round(value, 4)
    if isinstance(value, list):
        return [round_coords(item) for item in value]
    return value


def round_float(value: Any, digits: int = 3) -> Any:
    return None if value is None else round(float(value), digits)


def trim(feature: dict, properties: Optional[dict] = None) -> dict:
    return {
        "type": "Feature",
        "properties": properties if properties is not None else feature.get("properties", {}),
        "geometry": {
            "type": feature["geometry"]["type"],
            "coordinates": round_coords(feature["geometry"]["coordinates"]),
        },
    }


def collection(name: str, features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "name": name, "features": features}


def write(out: Path, name: str, payload: dict) -> None:
    path = out / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"  {name:28s} {path.stat().st_size / 1024:8.1f} KB")


def build_county(source: Path, out: Path) -> None:
    raw = load(source, "nyeri_county.geojson")
    features = [trim(f, {"name": f["properties"].get("name", "Nyeri")}) for f in raw["features"]]
    write(out, "county.geojson", collection("nyeri_county", features))


def build_sublocations(source: Path, out: Path) -> int:
    """The demand layer: population and density per sublocation, which is the
    finest administrative unit the platform can name a shopper's area by."""
    raw = load(source, "nyeri_sublocations.geojson")
    features = []
    for f in raw["features"]:
        props = f["properties"]
        label = (props.get("sublocation") or "").strip()
        features.append(
            trim(
                f,
                {
                    "name": label or None,
                    "population": props.get("population"),
                    "density": props.get("density"),
                    "area_km2": props.get("area_km2"),
                },
            )
        )
    fill_missing_names(features)
    features.sort(key=lambda f: (f["properties"]["density"] or 0), reverse=True)
    write(out, "sublocations.geojson", collection("nyeri_sublocations", features))
    return len(features)


def build_anchors(source: Path, out: Path) -> int:
    """Demand anchors: markets, universities, schools, banks, shops. These are
    what the study calls trip generators, as opposed to population which is
    where the trips start."""
    raw = load(source, "osm_pois.geojson")
    features = []
    for f in raw["features"]:
        props = f["properties"]
        lat = round(float(f["geometry"]["coordinates"][1]), 4)
        lng = round(float(f["geometry"]["coordinates"][0]), 4)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": props.get("name") or props.get("top_tag") or props.get("category"),
                    "category": props.get("category"),
                },
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
            }
        )
    write(out, "anchors.geojson", collection("nyeri_anchors", features))
    return len(features)


def build_suitability(source: Path, out: Path) -> int:
    """The study's scored 1 km grid, thinned to the cells worth drawing."""
    raw = load(source, "suitability_grid.geojson")
    features = []
    for f in raw["features"]:
        props = f["properties"]
        if (props.get("suitability") or 0) < SUITABILITY_FLOOR:
            continue
        features.append(trim(f, {"suitability": props.get("suitability"), "pop": props.get("pop")}))
    features.sort(key=lambda f: f["properties"]["suitability"], reverse=True)
    write(out, "suitability.geojson", collection("nyeri_suitability", features))
    return len(features)


def build_candidates(source: Path, out: Path) -> int:
    """The study's answer: its top cells at least 3 km apart, with the factor
    breakdown kept so the page can show *why* a site scored what it scored."""
    raw = load(source, "suitability_grid.geojson")
    sites = []
    for f in raw["features"]:
        props = f["properties"]
        if not props.get("is_candidate"):
            continue
        # The grid carries the cell's own centre, so no centroid maths needed.
        lng, lat = props.get("cell_lng"), props.get("cell_lat")
        if lat is None or lng is None:
            continue
        sites.append(
            {
                "lat": round(lat, 5),
                "lng": round(lng, 5),
                "suitability": props.get("suitability"),
                "pop_1km": props.get("pop"),
                "poi_count_1_5km": props.get("poi_count"),
                "road_m": None if props.get("road_m") is None else round(props["road_m"]),
                "anchor_m": None if props.get("anchor_m") is None else round(props["anchor_m"]),
                "factors": {
                    "demand": round_float(props.get("f_demand")),
                    "access": round_float(props.get("f_access")),
                    "amenities": round_float(props.get("f_amenity")),
                    "anchor": round_float(props.get("f_anchor")),
                },
            }
        )
    sites.sort(key=lambda s: s["suitability"], reverse=True)
    payload = {
        "source": "Nyeri e-commerce suitability study (WorldPop 2020, KNBS 2019, OpenStreetMap)",
        "weights": {"demand": 0.40, "access": 0.20, "amenities": 0.20, "anchor": 0.20},
        "sites": sites,
    }
    write(out, "candidates.json", payload)
    return len(sites)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="study's data/processed dir")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="bundle destination")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(
            f"study output not found at {args.source}\n"
            "pass --source pointing at its data/processed directory."
        )

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"reading {args.source}")
    print(f"writing {args.out}")
    build_county(args.source, args.out)
    subs = build_sublocations(args.source, args.out)
    anchors = build_anchors(args.source, args.out)
    cells = build_suitability(args.source, args.out)
    sites = build_candidates(args.source, args.out)
    total = sum(p.stat().st_size for p in args.out.glob("*")) / 1024
    print(
        f"\nsub-locations {subs}  anchors {anchors}  scored cells >= {SUITABILITY_FLOOR}: {cells}"
        f"  candidate sites {sites}\nbundle {total:.1f} KB"
    )


if __name__ == "__main__":
    main()
