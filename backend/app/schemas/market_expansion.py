"""Response models for the admin Market Expansion tab.

The four map layers stay typed as plain JSON: they are GeoJSON documents the
frontend hands to Leaflet as-is, and wrapping every ring in a model would buy
nothing. Everything the page reads as a number or a label is typed.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class StudySummary(BaseModel):
    source: Optional[str] = None
    weights: Optional[Dict[str, float]] = None
    county: Optional[str] = None
    sublocations: int
    sublocation_polygons: int
    population: int
    scored_cells: int
    suitability_range: Optional[List[float]] = None
    anchors: int


class CandidateFactors(BaseModel):
    demand: Optional[float] = None
    access: Optional[float] = None
    amenities: Optional[float] = None
    anchor: Optional[float] = None


class CandidateSite(BaseModel):
    lat: float
    lng: float
    suitability: Optional[float] = None
    pop_1km: Optional[int] = None
    poi_count_1_5km: Optional[int] = None
    road_m: Optional[int] = None
    anchor_m: Optional[int] = None
    factors: CandidateFactors


class CoverageShop(BaseModel):
    id: str
    name: str
    county: Optional[str] = None
    town: Optional[str] = None
    lat: float
    lng: float
    status: str
    is_verified: bool


class SublocationCoverage(BaseModel):
    name: str
    population: Optional[int] = None
    density: Optional[float] = None
    area_km2: Optional[float] = None
    polygons: int = 1
    shops: int
    orders: int
    unserved: bool


class CoverageSummary(BaseModel):
    shops_pinned: int
    shops_active: int
    paid_orders: int
    paid_orders_attributed: int
    unserved_sublocations: int
    unserved_population: int
    anchor_count: int


class MarketExpansionCoverage(BaseModel):
    shops: List[CoverageShop]
    sublocations: List[SublocationCoverage]
    summary: CoverageSummary


class MarketExpansionRead(BaseModel):
    """Coverage is optional on purpose: the study is a committed bundle, the
    coverage beside it is a live join. A database fault must not blank the
    analysis, so the failure rides in the response instead of raising."""

    study: StudySummary
    layers: Dict[str, Any]
    candidates: List[CandidateSite]
    coverage: Optional[MarketExpansionCoverage] = None
    coverage_error: Optional[str] = None
