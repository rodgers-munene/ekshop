import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, Date, Boolean, Enum, ForeignKey,
    Integer, Text, BigInteger, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class EventType(str, enum.Enum):
    view = "view"
    click = "click"
    add_to_cart = "add_to_cart"
    remove_from_cart = "remove_from_cart"
    wishlist = "wishlist"
    purchase = "purchase"
    search = "search"
    review = "review"


class TrendDirection(str, enum.Enum):
    up = "up"
    down = "down"
    stable = "stable"


class IssueStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    session_id = Column(String(64), nullable=False)
    event_type = Column(Enum(EventType, native_enum=False), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"))
    query = Column(String(255))
    meta = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_user_events_user_id", "user_id"),
        Index("ix_user_events_session_id", "session_id"),
        Index("ix_user_events_event_type", "event_type"),
        Index("ix_user_events_created_at", "created_at"),
    )

    user = relationship("User", back_populates="events")
    product = relationship("Product", back_populates="events")
    category = relationship("Category", back_populates="events")


class ProductScore(Base):
    __tablename__ = "product_scores"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    views_7d = Column(Integer, default=0)
    clicks_7d = Column(Integer, default=0)
    carts_7d = Column(Integer, default=0)
    purchases_7d = Column(Integer, default=0)
    wishlists_7d = Column(Integer, default=0)
    trending_score = Column(String(15), default="0.0000")
    quality_score = Column(String(10), default="0.0000")
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    product = relationship("Product", back_populates="score")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    category_weights = Column(JSONB, default=dict)
    price_range_min = Column(String(20))
    price_range_max = Column(String(20))
    preferred_counties = Column(ARRAY(String))
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="preferences")


class SearchTerm(Base):
    __tablename__ = "search_terms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    term = Column(String(255), unique=True, nullable=False)
    count_7d = Column(Integer, default=0)
    count_30d = Column(Integer, default=0)
    trend = Column(Enum(TrendDirection, native_enum=False), default=TrendDirection.stable)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class HeroSlide(Base):
    __tablename__ = "hero_slides"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_url = Column(String(500), nullable=False)
    title = Column(String(100))
    link_url = Column(String(500))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(50))
    starts_at = Column(DateTime(timezone=True))
    ends_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    product = relationship("Product", back_populates="promotions")


class WeeklyAnalytics(Base):
    __tablename__ = "weekly_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start = Column(Date, unique=True, nullable=False)
    new_buyers = Column(Integer, default=0)
    returning_buyers = Column(Integer, default=0)
    new_sellers = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)
    total_revenue = Column(String(20), default="0.00")
    repeat_purchase_rate = Column(String(10), default="0.00")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class IssueReport(Base):
    __tablename__ = "issue_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    description = Column(Text, nullable=False)
    status = Column(Enum(IssueStatus, native_enum=False), default=IssueStatus.open, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="issue_reports")


class ProductRequest(Base):
    __tablename__ = "product_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    requested_product = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="product_requests")
