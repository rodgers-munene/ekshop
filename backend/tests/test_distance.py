"""Road distance must be road distance (spec §3.2).

The pricing code used to call the Haversine great-circle formula, which
undercharges by 20-40% in built-up areas. These tests exist to make that
impossible to reintroduce silently.
"""
import httpx
import pytest

from app.services import distance as ds

NAIROBI = ds.GeoPoint(lat=-0.419, lng=36.955)
DEKUT = ds.GeoPoint(lat=-0.4279, lng=36.8814)

OSRM_OK = {"code": "Ok", "routes": [{"distance": 8215.4, "duration": 1043.2}], "waypoints": []}


def osrm_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- coordinate validation -----------------------------------------------------

@pytest.mark.parametrize(
    "lat,lng",
    [(-91.0, 36.9), (91.0, 36.9), (-0.4, 181.0), (-0.4, -181.0)],
)
def test_out_of_range_coordinates_are_rejected(lat, lng):
    with pytest.raises(ValueError):
        ds.GeoPoint(lat=lat, lng=lng)


# --- straight line stays flagged ------------------------------------------------

def test_straight_line_is_always_approximate():
    result = ds.StraightLineProvider().road_distance(NAIROBI, DEKUT)
    assert result.metres > 0
    assert result.approximate is True
    assert result.source == ds.DistanceSource.straight_line
    assert result.duration_seconds is None


def test_haversine_matches_a_known_distance():
    """One degree of latitude is about 111.19 km."""
    metres = ds.haversine_metres(ds.GeoPoint(0.0, 0.0), ds.GeoPoint(1.0, 0.0))
    assert abs(metres / 1000 - 111.19) < 0.5


def test_identical_points_are_zero():
    assert ds.haversine_metres(NAIROBI, NAIROBI) == 0.0


# --- OSRM parsing ---------------------------------------------------------------

def test_osrm_response_is_parsed():
    provider = ds.OSRMProvider(base_url="http://osrm.test", client=osrm_client(lambda r: httpx.Response(200, json=OSRM_OK)))
    result = provider.road_distance(NAIROBI, DEKUT)
    assert result.metres == pytest.approx(8215.4)
    assert result.duration_seconds == pytest.approx(1043.2)
    assert result.approximate is False
    assert result.source == ds.DistanceSource.osrm


def test_osrm_receives_longitude_then_latitude():
    """OSRM's order is the reverse of everywhere else here, and getting it
    wrong puts the rider somewhere in the Indian Ocean."""
    seen = {}

    def handler(request):
        path = request.url.path
        assert path.startswith("/route/v1/driving/"), path
        first = path.rsplit("/", 1)[-1].split(";")[0].split(",")
        seen["lng"], seen["lat"] = float(first[0]), float(first[1])
        return httpx.Response(200, json=OSRM_OK)

    provider = ds.OSRMProvider(base_url="http://osrm.test", client=osrm_client(handler))
    provider.road_distance(NAIROBI, DEKUT)
    assert seen["lng"] == pytest.approx(NAIROBI.lng)
    assert seen["lat"] == pytest.approx(NAIROBI.lat)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(200, json={"code": "Ok", "routes": []}),
        httpx.Response(200, json={"code": "NoRoute", "message": "no route"}),
        httpx.Response(200, text="not json"),
    ],
    ids=["server-error", "no-routes", "non-ok-code", "malformed-body"],
)
def test_osrm_failures_raise_distance_error(response):
    provider = ds.OSRMProvider(
        base_url="http://osrm.test", client=osrm_client(lambda r: response)
    )
    with pytest.raises(ds.DistanceError):
        provider.road_distance(NAIROBI, DEKUT)


# --- the guard -------------------------------------------------------------------

def test_pricing_refuses_an_approximate_distance():
    straight = ds.StraightLineProvider().road_distance(NAIROBI, DEKUT)
    with pytest.raises(ds.DistanceError, match="approximate"):
        ds.require_firm_distance(straight)


def test_pricing_accepts_a_real_road_distance():
    provider = ds.OSRMProvider(base_url="http://osrm.test", client=osrm_client(lambda r: httpx.Response(200, json=OSRM_OK)))
    real = provider.road_distance(NAIROBI, DEKUT)
    assert ds.require_firm_distance(real) is real


# --- fallback is flagged, never silent -------------------------------------------

def test_fallback_is_flagged_approximate():
    class Broken:
        name = "broken"

        def road_distance(self, origin, destination):
            raise ds.DistanceError("provider down")

    result = ds.get_road_distance(NAIROBI, DEKUT, provider=Broken())
    assert result.approximate is True
    assert result.source == ds.DistanceSource.straight_line
    with pytest.raises(ds.DistanceError):
        ds.require_firm_distance(result)


# --- caching ----------------------------------------------------------------------

def test_second_lookup_is_served_from_cache():
    ds.clear_cache()
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=OSRM_OK)

    provider = ds.OSRMProvider(base_url="http://osrm.test", client=osrm_client(handler))
    first = ds.get_road_distance(NAIROBI, DEKUT, provider=provider)
    second = ds.get_road_distance(NAIROBI, DEKUT, provider=provider)

    assert calls["n"] == 1, "the provider should be called once"
    assert first.metres == second.metres
    assert second.source == ds.DistanceSource.cache
    # A cache hit must not launder an approximate result into a firm one.
    assert second.approximate == first.approximate


def test_identical_points_short_circuit():
    ds.clear_cache()
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=OSRM_OK)

    provider = ds.OSRMProvider(base_url="http://osrm.test", client=osrm_client(handler))
    result = ds.get_road_distance(NAIROBI, NAIROBI, provider=provider)
    assert result.metres == 0.0
    assert calls["n"] == 0


# --- provider selection -----------------------------------------------------------

def test_osrm_is_the_default():
    assert isinstance(ds.get_provider(), ds.OSRMProvider)


def test_straight_line_can_be_selected_explicitly():
    assert isinstance(ds.get_provider("straight_line"), ds.StraightLineProvider)


def test_unknown_provider_is_rejected():
    with pytest.raises(ds.DistanceError):
        ds.get_provider("carrier_pigeon")