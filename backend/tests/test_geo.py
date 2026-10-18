"""Tests for hyperlocal discovery: the distance maths, the radius rule, the ranking.

No database is involved. The radius decision is a pure function (``_apply_radius``)
and the ranking is pure Python, so both are exercised directly; the SQL formula is
checked by inspecting the statement it compiles to, since asserting its *value*
would need Postgres and the point here is that the right formula is wired up at
all.
"""
import uuid
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.routers.catalog import _apply_radius
from app.services import recommendations as rec_service
from app.services.distance import GeoPoint, haversine_metres
from app.services.geo import (
    EARTH_RADIUS_KM,
    distance_km,
    distance_km_expr,
    proximity_weight,
    within_radius,
)


def _sql(expr) -> str:
    return str(expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


class TestProximityWeight:
    def test_bands_step_down_with_distance(self):
        assert proximity_weight(0.0, 30.0) == 5.0
        assert proximity_weight(2.0, 30.0) == 5.0
        assert proximity_weight(2.1, 30.0) == 3.5
        assert proximity_weight(5.0, 30.0) == 3.5
        assert proximity_weight(5.1, 30.0) == 2.0
        assert proximity_weight(30.0, 30.0) == 2.0
        assert proximity_weight(30.1, 30.0) == 1.0

    def test_unknown_distance_is_neutral_never_nearest(self):
        # A shop with no pin must not outrank a pinned shop 1 km away. Treating
        # "unknown" as 0 km would do exactly that, on a catalogue that is mostly
        # unpinned at launch, so it is pinned here.
        assert proximity_weight(None, 30.0) == 1.0
        assert proximity_weight(None, 30.0) < proximity_weight(1.0, 30.0)

    def test_boost_is_bounded(self):
        for away in (None, 0.0, 1.0, 12.0, 500.0):
            assert 1.0 <= proximity_weight(away, 30.0) <= 5.0


class TestDistanceKm:
    def test_same_point_is_zero(self):
        assert distance_km(-1.2921, 36.8219, -1.2921, 36.8219) == 0.0

    def test_matches_independent_haversine(self):
        metres = haversine_metres(GeoPoint(-1.2921, 36.8219), GeoPoint(-0.4169, 36.9510))
        assert distance_km(-1.2921, 36.8219, -0.4169, 36.9510) == round(metres / 1000.0, 1)

    def test_one_degree_of_latitude_is_about_111_km(self):
        assert 110.0 < distance_km(0.0, 0.0, 1.0, 0.0) < 112.0

    def test_missing_destination_yields_none_not_zero(self):
        # The whole point: `None` propagates to the API as "unknown distance".
        # A 0.0 here would render as "0 km away" on a card.
        assert distance_km(-1.2921, 36.8219, None, 36.9510) is None
        assert distance_km(-1.2921, 36.8219, -0.4169, None) is None


class TestRadiusSql:
    def test_distance_expr_uses_haversine_and_the_shops_own_columns(self):
        sql = _sql(distance_km_expr(-1.2921, 36.8219))
        assert "shops.lat" in sql and "shops.lng" in sql
        assert "radians" in sql and "asin" in sql and "sqrt" in sql
        # 2 * R, as the haversine formula renders it.
        assert str(2 * EARTH_RADIUS_KM) in sql

    def test_least_clamps_the_asin_domain(self):
        # Rounding can push h a hair above 1.0, and asin(1.0000001) is a database
        # error, not an approximate answer -- on a page load, for the shopper who
        # happens to sit exactly on a shop's pin.
        assert "least(1" in _sql(distance_km_expr(-1.2921, 36.8219)).lower()

    def test_radius_clause_requires_coordinates(self):
        sql = _sql(within_radius(-1.2921, 36.8219, 30.0))
        assert "shops.lat IS NOT NULL" in sql
        assert "shops.lng IS NOT NULL" in sql

    def test_radius_clause_bounds_both_axes(self):
        sql = _sql(within_radius(-1.2921, 36.8219, 30.0))
        assert "shops.lat BETWEEN" in sql
        assert "shops.lng BETWEEN" in sql
        # 30 km / 111.32 km-per-degree is 0.2695 degrees either side of -1.2921.
        assert "-1.561" in sql
        assert "-1.022" in sql

    def test_wider_radius_widens_the_box(self):
        narrow = _sql(within_radius(0.0, 0.0, 5.0))
        wide = _sql(within_radius(0.0, 0.0, 30.0))
        assert narrow != wide
        assert "-0.044" in narrow
        assert "-0.269" in wide


class _FakeQuery:
    """Just enough of a query to answer the one question _apply_radius asks."""

    def __init__(self, found, calls=None):
        self.found = found
        self.calls = calls if calls is not None else []

    def filter(self, *args, **kwargs):
        self.calls.append(args)
        return _FakeQuery(self.found, self.calls)

    def limit(self, n):
        assert n == 1, "the probe must ask for one row, not count the table"
        return self

    def first(self):
        return object() if self.found else None


class TestApplyRadius:
    def test_applies_radius_when_something_is_in_range(self):
        base = _FakeQuery(found=True)
        query, radius = _apply_radius(base, -1.2921, 36.8219, 30.0)
        assert query is not base
        assert radius == 30.0
        assert len(base.calls) == 1

    def test_drops_radius_when_nothing_is_in_range(self):
        # The launch-area case: pinned shops exist, but none of them sell anything
        # the buyer can see. An empty grid is a worse answer than a far-away grid.
        base = _FakeQuery(found=False)
        query, radius = _apply_radius(base, -1.2921, 36.8219, 30.0)
        assert query is base
        assert radius is None


def _product(name, county, lat=None, lng=None, trending=10.0):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        score=SimpleNamespace(trending_score=str(trending)),
        shop=SimpleNamespace(county=county, lat=lat, lng=lng),
    )


class TestRankWithGeoBoost:
    # Nyeri town, and a point ~1 km north of it.
    NYERI = (-0.4169, 36.9510)
    NEAR = (-0.4080, 36.9510)

    def test_nearer_product_outranks_farther_one_with_equal_score(self):
        near = _product("near", "Nyeri", *self.NEAR)
        far = _product("far", "Nairobi", -1.2921, 36.8219)
        ranked = rec_service._rank_with_geo_boost(
            [far, near], "Nyeri", 2, origin=GeoPoint(-0.4169, 36.9510)
        )
        assert [p.name for p in ranked] == ["near", "far"]

    def test_proximity_never_removes_a_product(self):
        products = [
            _product("a", "Nyeri", *self.NEAR),
            _product("b", "Nairobi", -1.2921, 36.8219),
            _product("c", "Garissa", -0.4536, 39.6461),
        ]
        ranked = rec_service._rank_with_geo_boost(
            products, "Nyeri", 3, origin=GeoPoint(*self.NYERI)
        )
        assert {p.name for p in ranked} == {"a", "b", "c"}

    def test_unpinned_shop_is_not_boosted_above_a_near_one(self):
        unpinned = _product("unpinned", "Nyeri")
        near = _product("near", "Nyeri", *self.NEAR)
        ranked = rec_service._rank_with_geo_boost(
            [unpinned, near], "Nyeri", 2, origin=GeoPoint(*self.NYERI)
        )
        assert ranked[0].name == "near"
        assert ranked[1].name == "unpinned"

    def test_strong_trending_still_beats_a_near_but_weak_product(self):
        # Proximity is a nudge on the trending score, not a replacement for it:
        # a 1 km product with no traction should not outrank a best-seller 40 km
        # away, or "near me" quietly becomes "only me".
        weak_near = _product("weak-near", "Nyeri", *self.NEAR, trending=1.0)
        strong_far = _product("strong-far", "Nairobi", -1.2921, 36.8219, trending=100.0)
        ranked = rec_service._rank_with_geo_boost(
            [weak_near, strong_far], "Nyeri", 2, origin=GeoPoint(*self.NYERI)
        )
        assert ranked[0].name == "strong-far"

    def test_county_boost_still_applies_without_a_coordinate(self):
        same_county = _product("same", "Nyeri")
        other_county = _product("other", "Garissa")
        ranked = rec_service._rank_with_geo_boost([other_county, same_county], "Nyeri", 2)
        assert ranked[0].name == "same"

    def test_no_signal_at_all_leaves_the_pool_untouched(self):
        products = [_product("a", "Nyeri"), _product("b", "Garissa")]
        ranked = rec_service._rank_with_geo_boost(products, None, 2)
        assert ranked == products

    def test_limit_is_respected(self):
        products = [_product(f"p{i}", "Nyeri", *self.NEAR) for i in range(6)]
        ranked = rec_service._rank_with_geo_boost(
            products, "Nyeri", 3, origin=GeoPoint(*self.NYERI)
        )
        assert len(ranked) == 3
