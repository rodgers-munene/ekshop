"""The Market Expansion tab compares a fixed study against live coverage.

Two joins make that comparison possible, and both are easy to get silently
wrong:

* sublocation names. The study's polygons are UPPERCASE with occasional double
  spaces ("Othaya  Township"), while shop addresses resolved through the
  boundary loader and order snapshots are proper-case with single spaces.
  Matching naively leaves shopless gaps everywhere; matching after collapsing
  whitespace and case is what makes "196 sublocations, 3 shops" true.
* shop coordinates. The boundary loader has to test a point against every ward
  polygon in Kenya, so only pins inside the study's bounding box are worth
  resolving -- and a shop in Mombasa must never be attributed to a Nyeri
  sublocation.

The study bundle itself is committed, so these tests read the real files and pin
the numbers the page reports.
"""
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.shop import Shop, ShopStatus
from app.services import market_expansion as mx


class FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *criteria):
        return self

    def group_by(self, *criteria):
        return self

    def all(self):
        return self._rows


class FakeSession:
    """Enough of a Session for the two aggregate queries coverage runs: one over
    shops, one grouped by the order snapshot's sublocation."""

    def __init__(self, shops=(), order_rows=()):
        self._shops = list(shops)
        self._order_rows = list(order_rows)

    def query(self, *entities):
        return FakeQuery(self._shops if entities[0] is Shop else self._order_rows)


def shop(lat, lng, name="Shop", status=ShopStatus.active):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        county="Nyeri",
        town="Nyeri",
        lat=lat,
        lng=lng,
        status=status,
        is_verified=True,
    )


@pytest.fixture(autouse=True)
def clear_study_cache():
    """`load_study` memoises process-wide; a test that points BUNDLE_DIR at an
    empty directory must not leave that answer cached for the next one."""
    mx._cache = None
    yield
    mx._cache = None


@pytest.fixture
def resolve(monkeypatch):
    """Stub the boundary loader and record every point it is asked about."""
    calls = []

    def install(mapping):
        def fake(lat, lng):
            calls.append((lat, lng))
            return mapping.get((lat, lng))

        monkeypatch.setattr(mx, "_resolve_sublocation", fake)
        return calls

    return install


class TestStudyBundle:
    def test_bundle_is_present_and_shaped(self):
        study = mx.load_study()
        assert study is not None, "run backend/scripts/export_market_expansion.py"
        assert study["summary"]["county"] == "Nyeri"
        # 196 sublocation polygons for the county, 12 candidate sites apart from
        # each other by at least the study's separation rule.
        assert len(study["layers"]["sublocations"]["features"]) == 196
        assert len(study["candidates"]["sites"]) == 12

    def test_every_sublocation_polygon_has_a_name(self):
        """One polygon arrives unnamed from the KNBS source; the exporter labels
        it from its parent location so the map has no anonymous demand area and
        no area silently missing from the coverage table."""
        study = mx.load_study()
        for feature in study["layers"]["sublocations"]["features"]:
            assert (feature["properties"]["name"] or "").strip()

    def test_sublocation_layer_carries_demand_not_polygons_alone(self):
        study = mx.load_study()
        for feature in study["layers"]["sublocations"]["features"]:
            props = feature["properties"]
            assert props["name"]
            assert props["population"] is not None
            assert props["density"] is not None

    def test_study_thins_the_grid_before_shipping_it(self):
        """The whole scored grid is 3027 cells; only the top of it is worth
        680 KB in git and a slower first paint."""
        study = mx.load_study()
        scores = [f["properties"]["suitability"] for f in study["layers"]["suitability"]["features"]]
        assert scores
        assert len(scores) < 3027
        # The floor the exporter drops below (SUITABILITY_FLOOR in
        # scripts/export_market_expansion.py).
        assert min(scores) >= 55

    def test_candidates_are_ranked_and_inside_the_county(self):
        study = mx.load_study()
        bounds = mx._bounds(study["layers"]["county"])
        sites = study["candidates"]["sites"]
        scores = [site["suitability"] for site in sites]
        assert scores == sorted(scores, reverse=True)
        for site in sites:
            assert mx._inside(bounds, site["lat"], site["lng"])
            assert 0 <= site["suitability"] <= 100
            assert set(site["factors"]) == {"demand", "access", "amenities", "anchor"}

    def test_anchors_are_points_inside_the_county(self):
        study = mx.load_study()
        bounds = mx._bounds(study["layers"]["county"])
        features = study["layers"]["anchors"]["features"]
        assert features
        for feature in features:
            lat = feature["geometry"]["coordinates"][1]
            lng = feature["geometry"]["coordinates"][0]
            assert mx._inside(bounds, lat, lng)


class TestNameMatching:
    def test_admin_names_are_normalised_before_matching(self):
        study = mx.load_study()
        table = mx._study_sublocations(study["layers"]["sublocations"]["features"])
        assert all(key == mx._clean(key) for key in table)
        # ...and the study's own names are the form that needs normalising.
        raw = {f["properties"]["name"] for f in study["layers"]["sublocations"]["features"]}
        assert any(name != mx._clean(name) for name in raw if name)

    def test_duplicate_names_collapse_to_one_bucket(self):
        study = mx.load_study()
        features = study["layers"]["sublocations"]["features"]
        table = mx._study_sublocations(features)
        # Nyeri has a handful of sublocation names repeated across subcounties.
        assert len(table) < len(features)

    def test_a_repeated_name_adds_up_instead_of_overwriting(self):
        study = mx.load_study()
        features = study["layers"]["sublocations"]["features"]
        table = mx._study_sublocations(features)
        merged = next(entry for entry in table.values() if entry["polygons"] > 1)
        originals = [
            f["properties"]
            for f in features
            if mx._clean(f["properties"]["name"]) == mx._clean(merged["name"])
        ]
        assert len(originals) == merged["polygons"]
        assert merged["population"] == sum(p["population"] for p in originals)
        assert merged["density"] == round(
            merged["population"] / merged["area_km2"], 1
        )


class TestCoverage:
    def _study(self):
        return mx.load_study()

    def _name(self, most_populous=True):
        study = self._study()
        rows = sorted(
            study["layers"]["sublocations"]["features"],
            key=lambda f: f["properties"]["population"] or 0,
            reverse=most_populous,
        )
        return rows[0]["properties"]["name"]

    def test_shop_pins_are_attributed_by_resolved_sublocation(self, resolve):
        name = self._name()
        calls = resolve({(-0.42, 36.95): name.lower()})
        session = FakeSession(shops=[shop(-0.42, 36.95)])
        coverage = mx.build_coverage(session, self._study())
        assert calls == [(-0.42, 36.95)]
        row = next(r for r in coverage["sublocations"] if r["name"] == name)
        assert row["shops"] == 1
        assert coverage["summary"]["shops_pinned"] == 1

    def test_shops_outside_the_county_are_neither_listed_nor_resolved(self, resolve):
        calls = resolve({})
        session = FakeSession(shops=[shop(-1.29, 36.82, name="Nairobi Shop")])
        coverage = mx.build_coverage(session, self._study())
        assert calls == []
        assert coverage["shops"] == []
        assert coverage["summary"]["shops_pinned"] == 0

    def test_order_snapshots_join_on_the_same_normalised_name(self, resolve):
        resolve({})
        name = self._name()
        session = FakeSession(order_rows=[(f"  {name.lower()}  ", 3)])
        coverage = mx.build_coverage(session, self._study())
        row = next(r for r in coverage["sublocations"] if r["name"] == name)
        assert row["orders"] == 3
        assert coverage["summary"]["paid_orders_attributed"] == 3

    def test_orders_outside_the_study_are_counted_but_not_attributed(self, resolve):
        resolve({})
        session = FakeSession(order_rows=[("KILIMANI", 2), ("NYERI TOWN", 1)])
        coverage = mx.build_coverage(session, self._study())
        summary = coverage["summary"]
        assert summary["paid_orders"] == 3
        assert summary["paid_orders_attributed"] <= 3

    def test_unserved_means_people_with_no_shop_on_the_platform(self, resolve):
        resolve({})
        study = self._study()
        rows = study["layers"]["sublocations"]["features"]
        busy = max(rows, key=lambda f: f["properties"]["population"])["properties"]["name"]
        quiet = min(
            (f for f in rows if f["properties"]["population"]),
            key=lambda f: f["properties"]["population"],
        )["properties"]["name"]
        coverage = mx.build_coverage(FakeSession(), study)
        by_name = {row["name"]: row for row in coverage["sublocations"]}
        # A busy sublocation with nobody selling is the find the tab exists for.
        assert by_name[busy]["shops"] == 0
        assert by_name[busy]["unserved"] is True
        # A quiet one is not worth a van and must not be flagged.
        assert by_name[quiet]["population"] < mx.UNSERVED_POPULATION
        assert by_name[quiet]["unserved"] is False

    def test_a_single_shop_clears_the_flag(self, resolve):
        study = self._study()
        busy = max(
            study["layers"]["sublocations"]["features"],
            key=lambda f: f["properties"]["population"],
        )["properties"]["name"]
        resolve({(-0.42, 36.95): busy})
        coverage = mx.build_coverage(FakeSession(shops=[shop(-0.42, 36.95)]), study)
        row = next(r for r in coverage["sublocations"] if r["name"] == busy)
        assert row["shops"] == 1
        assert row["unserved"] is False
        assert coverage["summary"]["shops_active"] == 1

    def test_sublocations_are_listed_biggest_first(self, resolve):
        resolve({})
        coverage = mx.build_coverage(FakeSession(), self._study())
        pops = [row["population"] for row in coverage["sublocations"]]
        assert pops == sorted(pops, reverse=True)

    def test_summary_adds_up(self, resolve):
        resolve({})
        study = self._study()
        coverage = mx.build_coverage(FakeSession(), study)
        summary = coverage["summary"]
        assert summary["anchor_count"] == len(study["layers"]["anchors"]["features"])
        assert summary["unserved_sublocations"] == sum(
            1 for row in coverage["sublocations"] if row["unserved"]
        )
        assert summary["unserved_population"] == sum(
            row["population"] for row in coverage["sublocations"] if row["unserved"]
        )


class TestReport:
    def test_report_returns_every_layer_the_page_draws(self, resolve):
        resolve({})
        report = mx.build_report(FakeSession())
        assert report is not None
        assert set(report["layers"]) == {"county", "sublocations", "anchors", "suitability"}
        assert report["study"]["county"] == "Nyeri"
        assert report["study"]["anchors"] == len(report["layers"]["anchors"]["features"])
        assert len(report["candidates"]) == 12
        assert report["coverage"]["summary"]["shops_pinned"] == 0

    def test_a_missing_bundle_is_reported_not_raised(self, resolve, monkeypatch, tmp_path: Path):
        """The API answers 503 with instructions; it must not 500 while the
        exporter has not been run on a fresh checkout."""
        resolve({})
        monkeypatch.setattr(mx, "BUNDLE_DIR", tmp_path / "market_expansion")
        assert mx.load_study() is None
        assert mx.build_report(FakeSession()) is None
