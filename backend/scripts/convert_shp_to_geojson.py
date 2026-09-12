import json
import os
import shapefile
from pyproj import Transformer

BASE = r"D:\EKSHOP-STORE\ekshop\backend\Data"
OUT = os.path.join(BASE, "geojson")
os.makedirs(OUT, exist_ok=True)


def ring_signed_area(ring):
    s = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def point_in_ring(px, py, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > py) != (yj > py):
            xint = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < xint:
                inside = not inside
        j = i
    return inside


def ring_samples(ring):
    mid = (len(ring) - 1) // 2
    cxs = sum(p[0] for p in ring) / len(ring)
    cys = sum(p[1] for p in ring) / len(ring)
    return [ring[0], ring[mid], (cxs, cys)]


def ring_contained_in(ring_a, ring_b):
    for px, py in ring_samples(ring_a):
        if not point_in_ring(px, py, ring_b):
            return False
    return True


def shapefile_to_geometry(shp, transform=None):
    parts = list(shp.parts) + [len(shp.points)]
    rings = [shp.points[parts[i]:parts[i + 1]] for i in range(len(shp.parts))]
    if transform is not None:
        rings = [[(px, py) for px, py in transform.itransform(zip([p[0] for p in r], [p[1] for p in r]))] for r in rings]
    rings = [r for r in rings if len(r) >= 4]
    if not rings:
        return None, None

    shells = []
    holes = []
    for i, r in enumerate(rings):
        contained = any(
            j != i and abs(ring_signed_area(rings[j])) > abs(ring_signed_area(r))
            and ring_contained_in(r, rings[j])
            for j in range(len(rings))
        )
        (holes if contained else shells).append(r)

    # assign holes to the smallest containing shell
    polys = [{"shell": s, "holes": [], "area": abs(ring_signed_area(s))} for s in shells]
    for hole in holes:
        best = None
        for p in polys:
            if ring_contained_in(hole, p["shell"]) and abs(ring_signed_area(p["shell"])) > abs(ring_signed_area(hole)):
                if best is None or abs(ring_signed_area(p["shell"])) < abs(ring_signed_area(best["shell"])):
                    best = p
        if best is not None:
            best["holes"].append(hole)

    polys.sort(key=lambda p: p["area"], reverse=True)
    largest = polys[0]

    def centroid_of(shell):
        a = 0.0
        cx = 0.0
        cy = 0.0
        n = len(shell)
        for i in range(n):
            x1, y1 = shell[i]
            x2, y2 = shell[(i + 1) % n]
            cross = x1 * y2 - x2 * y1
            a += cross
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
        a /= 2.0
        if abs(a) < 1e-12:
            return [round(sum(p[0] for p in shell) / len(shell), 6), round(sum(p[1] for p in shell) / len(shell), 6)]
        return [round(cx / (6.0 * a), 6), round(cy / (6.0 * a), 6)]

    centroid = centroid_of(largest["shell"])

    def round_ring(r):
        return [[round(px, 6), round(py, 6)] for px, py in r]

    if len(polys) == 1:
        geom = {"type": "Polygon", "coordinates": [round_ring(largest["shell"])] + [round_ring(h) for h in largest["holes"]]}
    else:
        geom = {"type": "MultiPolygon", "coordinates": [
            [round_ring(p["shell"])] + [round_ring(h) for h in p["holes"]] for p in polys
        ]}
    return geom, centroid


def convert(src_path, properties_fn, dst_name, transform=None, build_index=False):
    sf = shapefile.Reader(src_path)
    features = []
    index_rows = []
    for i in range(len(sf)):
        rec = sf.record(i)
        shp = sf.shape(i)
        geom, centroid = shapefile_to_geometry(shp, transform)
        if geom is None:
            print(f"  skip {dst_name} feature {i}: no geometry")
            continue
        props = properties_fn(rec)
        features.append({"type": "Feature", "properties": props, "geometry": geom})
        if build_index:
            index_rows.append({**props, "centroid": centroid})
    sf.close()
    fc = {
        "type": "FeatureCollection",
        "name": dst_name,
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    with open(os.path.join(OUT, dst_name + ".geojson"), "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    return index_rows


sfc = shapefile.Reader(os.path.join(BASE, "Constituencies", "constituencies"))
county_codes = {}
for i in range(len(sfc)):
    r = sfc.record(i)
    name = str(r["COUNTY_NAM"]).strip().upper()
    if name and name not in county_codes:
        county_codes[name] = int(r["COUNTY_COD"])
sfc.close()

arc1960_to_wgs84 = Transformer.from_crs("EPSG:4210", "EPSG:4326", always_xy=True)

index_counties = convert(
    os.path.join(BASE, "Counties", "edited-counties"),
    lambda r: {
        "name": str(r["COUNTIES"]).strip(),
        "county_code": county_codes.get(str(r["COUNTIES"]).strip().upper()),
        "country": str(r["COUNTRY"]).strip(),
    },
    "kenya_counties",
    transform=arc1960_to_wgs84,
    build_index=True,
)

index_constituencies = convert(
    os.path.join(BASE, "Constituencies", "constituencies"),
    lambda r: {
        "constituency_code": int(r["CONST_CODE"]),
        "constituency": str(r["CONSTITUEN"]).strip(),
        "county": str(r["COUNTY_NAM"]).strip(),
        "county_code": int(r["COUNTY_COD"]),
    },
    "kenya_constituencies",
    build_index=True,
)

index_wards = convert(
    os.path.join(BASE, "Kenya_Wards", "kenya_wards"),
    lambda r: {
        "ward_code": str(r["uid"]).strip(),
        "ward": str(r["ward"]).strip(),
        "subcounty": str(r["subcounty"]).strip(),
        "subcounty_code": str(r["scuid"]).strip(),
        "county": str(r["county"]).strip(),
        "county_code": county_codes.get(str(r["county"]).strip().upper()),
        "population": int(r["pop2009"]),
    },
    "kenya_wards",
    build_index=True,
)

index_subcounties = convert(
    os.path.join(BASE, "ke_subcounty", "ke_subcounty"),
    lambda r: {
        "subcounty": str(r["subcounty"]).strip(),
        "subcounty_code": str(r["scpcode"]).strip(),
        "dhis2_id": str(r["dhis2_id"]).strip(),
        "county": str(r["county"]).strip(),
        "county_code": county_codes.get(str(r["county"]).strip().upper()),
        "province": str(r["province"]).strip(),
        "province_code": str(r["provpcode"]).strip(),
    },
    "kenya_subcounties",
    build_index=True,
)

index_locations = convert(
    os.path.join(BASE, "kenlocations", "Ken_Locations", "Ken_Locations"),
    lambda r: {
        "location": str(r["LOCNAME"]).strip(),
        "location_code": int(r["LOCID"]),
    },
    "kenya_locations",
    build_index=True,
)

index_sublocations = convert(
    os.path.join(BASE, "kensublocations", "Ken_Sublocations", "Ken_Sublocations"),
    lambda r: {
        "sublocation": str(r["SLNAME"]).strip(),
        "sublocation_code": int(r["SLID"]),
        "location_code": int(r["SLID"]) // 100,
    },
    "kenya_sublocations",
    build_index=True,
)

index = {
    "kenya_counties": index_counties,
    "kenya_constituencies": index_constituencies,
    "kenya_subcounties": index_subcounties,
    "kenya_wards": index_wards,
    "kenya_locations": index_locations,
    "kenya_sublocations": index_sublocations,
}
with open(os.path.join(OUT, "kenya_index.json"), "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=1)

for name in index:
    p = os.path.join(OUT, name + ".geojson")
    sz = os.path.getsize(p) / 1024 / 1024
    print(f"{name}.geojson  {sz:.2f} MB")
print(f"kenya_index.json  {os.path.getsize(os.path.join(OUT, 'kenya_index.json'))/1024:.1f} KB")
print("features:", {k: len(v) for k, v in index.items()})