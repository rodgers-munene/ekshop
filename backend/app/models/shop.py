import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Enum, ForeignKey, Integer, Float, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ShopStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"


class Shop(Base):
    __tablename__ = "shops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(String)
    logo_url = Column(String(500))
    banner_url = Column(String(500))
    county = Column(String(100))
    town = Column(String(100))
    lat = Column(Float)
    lng = Column(Float)
    ward_id = Column(UUID(as_uuid=True), ForeignKey("wards.id", ondelete="SET NULL"))
    exact_location = Column(String(255))
    phone = Column(String(20))
    rating_avg = Column(String(10), default="0.00")
    rating_count = Column(Integer, default=0)
    total_sales = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    status = Column(Enum(ShopStatus, native_enum=False), default=ShopStatus.pending, nullable=False)
    # Prep time management
    prep_time_minutes = Column(Integer, default=30, nullable=False)
    max_prep_time_minutes = Column(Integer, default=60, nullable=False)

    # --- Delivery subsidy settings (spec §10.1, Appendix B.1) ----------------
    # A merchant subsidy is a contribution *towards fulfilment*, never a product
    # discount: it must not reduce the order subtotal or appear as a sale. It
    # changes who bears the delivery cost, not the total delivery revenue.
    delivery_subsidy_enabled = Column(Boolean, default=False, nullable=False, server_default="0")
    # A fixed amount the merchant always contributes...
    delivery_subsidy_amount = Column(Numeric(12, 2), nullable=False, server_default="0")
    # ...and/or a threshold rule: at or above this basket value the merchant
    # covers up to `maximum_delivery_subsidy`, which can zero the customer's
    # payment entirely (§10.2).
    free_delivery_threshold = Column(Numeric(12, 2))
    maximum_delivery_subsidy = Column(Numeric(12, 2))
    # Caps the merchant's total exposure; the engine must not exceed it.
    weekly_subsidy_budget = Column(Numeric(12, 2))

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    seller = relationship("User", back_populates="shop")
    ward = relationship("Ward")
    payment_methods = relationship("ShopPaymentMethod", back_populates="shop", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="shop")
    orders = relationship("Order", back_populates="shop")
    reviews = relationship("ProductReview", back_populates="shop")
    return_requests = relationship("ReturnRequest", back_populates="shop", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="shop")
    subscription = relationship("Subscription", back_populates="shop", uselist=False)


class ShopPaymentMethod(Base):
    __tablename__ = "shop_payment_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    method = Column(String(100), nullable=False)
    details = Column(JSONB)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    shop = relationship("Shop", back_populates="payment_methods")
