"""Zone/pricing models with GIS/geospatial awareness.

These models replace hardcoded zone configurations with real database models
that support geospatial queries and are driven by the Excel/CSV reference data.
"""
import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography, Geometry
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_Contains, ST_MakePoint

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ZoneType(str, enum.Enum):
    """Type of delivery zone."""
    residential = "residential"      # Residential/hostel areas
    commercial = "commercial"        # Commercial/business areas
    institutional = "institutional"  # Schools, hospitals, etc.
    industrial = "industrial"        # Industrial zones
    mixed = "mixed"                  # Mixed-use areas


class PricingTier(str, enum.Enum):
    """Delivery pricing tiers."""
    free = "free"
    small = "small"
    medium = "medium"
    large = "large"
    oversized = "oversized"  # >20kg or special handling


class Zone(Base):
    """Delivery zone with geospatial boundaries and pricing rules.

    Each zone represents a geographic area with specific pricing rules.
    Zones are defined by polygons (PostGIS) and can overlap with priority.
    """
    __tablename__ = "delivery_zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(20), nullable=False, unique=True)  # e.g., "nyaribo", "embassy"
    zone_type = Column(Enum(ZoneType, native_enum=False), default=ZoneType.residential, nullable=False)
    description = Column(Text)

    # Geographic boundary as polygon (SRID 4326 = WGS84 lat/lng)
    boundary = Column(Geography(geometry_type="POLYGON", srid=4326), nullable=False)
    # Center point for quick distance calculations
    center_point = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)

    # Zone properties
    avg_distance_km = Column(Numeric(6, 2))  # Average delivery distance in zone
    priority = Column(Integer, default=0)  # Higher priority zones checked first

    # Free delivery threshold (basket value >= this = free delivery)
    free_delivery_threshold = Column(Numeric(12, 2))

    # Tier-specific fee ranges (stored as JSON for flexibility)
    # Format: {"free": {"min": 0, "max": 0}, "small": {"min": 20, "max": 50}, ...}
    tier_fee_ranges = Column(JSONB, nullable=False, default={})

    # Add-on fees
    addon_fragile_fee = Column(Numeric(8, 2), default=0)
    addon_rush_fee = Column(Numeric(8, 2), default=0)
    rush_time_minutes = Column(Integer, default=45)

    # Zone-specific settings
    avg_speed_kmh = Column(Numeric(4, 1))  # Average speed in zone
    is_active = Column(Boolean, default=True, nullable=False, server_default="1")
    is_default = Column(Boolean, default=False, nullable=False, server_default="0")  # Fallback zone

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    tier_configs = relationship("ZonePricingTier", back_populates="zone", cascade="all, delete-orphan")
    shops = relationship(
        "Shop",
        secondary="shop_zone_assignments",
        viewonly=True,
        lazy="select",
    )
    pricing_overrides = relationship("ZonePricingOverride", back_populates="zone", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_delivery_zones_boundary", "boundary", postgresql_using="gist"),
        Index("ix_delivery_zones_center", "center_point", postgresql_using="gist"),
        Index("ix_delivery_zones_active", "is_active"),
    )

    def __repr__(self):
        return f"<Zone {self.code}: {self.name}>"


class ZonePricingTier(Base):
    """Detailed pricing configuration for a specific tier within a zone."""
    __tablename__ = "zone_pricing_tiers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=False)
    tier = Column(Enum(PricingTier, native_enum=False), nullable=False)

    # Fee structure
    min_fee = Column(Numeric(10, 2), nullable=False)
    max_fee = Column(Numeric(10, 2), nullable=False)
    flat_fee = Column(Numeric(10, 2))  # If set, overrides min/max (flat rate)

    # Conditions for this tier
    min_weight_kg = Column(Numeric(8, 3), default=0)
    max_weight_kg = Column(Numeric(8, 3))  # None = no upper limit
    min_basket_value = Column(Numeric(12, 2), default=0)
    max_basket_value = Column(Numeric(12, 2))  # None = no upper limit

    # Item size constraints (for "small/medium/large" classification)
    max_dimension_cm = Column(Numeric(8, 1))  # Max dimension in cm
    max_volume_l = Column(Numeric(8, 1))      # Max volume in liters

    # Free if combined with higher tier
    free_if_combined_with = Column(JSONB, default=[])  # List of tier names

    # Distance modifier (multiplier for distance beyond base)
    distance_rate_multiplier = Column(Numeric(4, 3), default=1.0)

    is_active = Column(Boolean, default=True, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    zone = relationship("Zone", back_populates="tier_configs")

    __table_args__ = (
        UniqueConstraint("zone_id", "tier", name="uq_zone_tier"),
        Index("ix_zone_pricing_tiers_zone_active", "zone_id", "is_active"),
        CheckConstraint("min_fee <= max_fee", name="ck_tier_fee_order"),
    )

    def get_fee(self, weight_kg: Decimal = None, basket_value: Decimal = None) -> Decimal:
        """Calculate fee for given order parameters."""
        if self.flat_fee is not None:
            return self.flat_fee
        # Could add dynamic pricing based on weight/value here
        return self.max_fee  # Default to max for safety


class ZonePricingOverride(Base):
    """Zone-specific overrides for global pricing config parameters.

    Allows per-zone tuning of global pricing config parameters without changing
    the global config. Admin can override specific rates per zone.
    """
    __tablename__ = "zone_pricing_overrides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=False)

    # Parameter key (matches PricingConfig fields)
    parameter_key = Column(String(80), nullable=False)
    # Override value (stored as string, parsed by type)
    value = Column(String(80), nullable=False)
    value_type = Column(String(20), nullable=False)  # money, rate, integer, boolean, json

    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    zone = relationship("Zone", back_populates="pricing_overrides")

    __table_args__ = (
        UniqueConstraint("zone_id", "parameter_key", name="uq_zone_override"),
        Index("ix_zone_overrides_active", "zone_id", "is_active"),
    )


class ShopZoneAssignment(Base):
    """Assignment of shops to delivery zones with optional overrides.

    A shop can belong to multiple zones with different priorities.
    The highest priority active assignment is used for pricing.
    """
    __tablename__ = "shop_zone_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=False)

    # Priority: higher = checked first. Shop's own location determines primary zone.
    priority = Column(Integer, default=0)
    is_primary = Column(Boolean, default=False, nullable=False, server_default="0")
    is_active = Column(Boolean, default=True, nullable=False, server_default="1")

    # Optional shop-specific fee adjustments (percent or flat)
    fee_adjustment_percent = Column(Numeric(5, 2), default=0)
    fee_adjustment_flat = Column(Numeric(8, 2), default=0)

    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("shop_id", "zone_id", name="uq_shop_zone"),
        Index("ix_shop_zone_assignments_shop", "shop_id"),
        Index("ix_shop_zone_assignments_zone", "zone_id"),
        Index("ix_shop_zone_assignments_priority", "shop_id", "priority"),
    )


class CustomerZoneAssignment(Base):
    """Runtime assignment of customers/delivery addresses to zones.

    Used at quote time to determine which zone pricing applies.
    Can be cached and refreshed periodically.
    """
    __tablename__ = "customer_zone_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Can reference user, or be standalone for guest checkouts
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    # For guest orders: lat/lng of delivery address
    lat = Column(Numeric(9, 6))
    lng = Column(Numeric(9, 6))

    zone_id = Column(UUID(as_uuid=True), ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=False)

    # How this assignment was determined
    assignment_method = Column(String(30))  # geofence, manual, fallback, ip_geolocation
    confidence = Column(Numeric(4, 3))  # 0-1 confidence score

    is_active = Column(Boolean, default=True, nullable=False, server_default="1")
    assigned_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True))  # Cache expiry

    __table_args__ = (
        Index("ix_customer_zone_user", "user_id"),
        Index("ix_customer_zone_zone", "zone_id"),
        Index("ix_customer_zone_expires", "expires_at"),
        Index("ix_customer_zone_location", "lat", "lng"),
    )


class ZoneAnalytics(Base):
    """Aggregated analytics per zone for monitoring and optimization.

    Updated periodically by cron jobs. Not real-time.
    """
    __tablename__ = "zone_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=False)

    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # Order metrics
    total_orders = Column(Integer, default=0)
    completed_orders = Column(Integer, default=0)
    cancelled_orders = Column(Integer, default=0)

    # Revenue metrics
    total_revenue = Column(Numeric(14, 2), default=0)
    total_delivery_fees = Column(Numeric(14, 2), default=0)
    total_subsidies = Column(Numeric(14, 2), default=0)

    # Tier distribution
    tier_distribution = Column(JSONB, default={})  # {"small": 10, "medium": 5, ...}

    # Performance metrics
    avg_delivery_time_min = Column(Numeric(8, 1))
    avg_distance_km = Column(Numeric(8, 2))
    on_time_rate = Column(Numeric(5, 2))

    # Economics
    avg_contribution_per_order = Column(Numeric(10, 2))
    total_contribution = Column(Numeric(14, 2), default=0)
    loss_making_orders = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("zone_id", "period_start", "period_end", name="uq_zone_analytics_period"),
        Index("ix_zone_analytics_period", "period_start", "period_end"),
    )


# GIS utility functions for zone queries
def get_zone_for_point(db, lat: float, lng: float):
    """Find the highest priority active zone containing the given point."""
    from sqlalchemy import select
    from geoalchemy2.functions import ST_Contains

    point = func.ST_MakePoint(lng, lat)
    point = func.ST_SetSRID(point, 4326)

    stmt = (
        select(Zone)
        .where(Zone.is_active == True)
        .where(func.ST_Contains(Zone.boundary, point))
        .order_by(Zone.priority.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_zones_near_point(db, lat: float, lng: float, radius_km: float = 5):
    """Find all zones within radius_km of a point."""
    from sqlalchemy import select
    from geoalchemy2.functions import ST_DWithin

    point = func.ST_MakePoint(lng, lat)
    point = func.ST_SetSRID(point, 4326)
    radius_m = radius_km * 1000

    stmt = (
        select(Zone)
        .where(Zone.is_active == True)
        .where(func.ST_DWithin(Zone.boundary, point, radius_m))
        .order_by(Zone.priority.desc())
    )
    return db.execute(stmt).scalars().all()


def get_zone_by_code(db, code: str):
    """Get zone by code (e.g., 'nyaribo', 'embassy')."""
    from sqlalchemy import select
    stmt = select(Zone).where(Zone.code == code).where(Zone.is_active == True)
    return db.execute(stmt).scalar_one_or_none()