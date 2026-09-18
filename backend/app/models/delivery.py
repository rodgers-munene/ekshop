import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class DeliveryAgentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    busy = "busy"


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    assigned = "assigned"
    picked = "picked"
    in_transit = "in_transit"
    delivered = "delivered"
    cancelled = "cancelled"


class ActorRole(str, enum.Enum):
    customer = "customer"
    agent = "agent"
    admin = "admin"


class DeliveryAgent(Base):
    __tablename__ = "delivery_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    password_hash = Column(String(255), nullable=False)
    status = Column(Enum(DeliveryAgentStatus, native_enum=False), default=DeliveryAgentStatus.active)
    current_order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"))
    total_deliveries = Column(Integer, default=0)
    rating_avg = Column(String(5), default="5.00")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    current_order = relationship("Order", foreign_keys=[current_order_id])
    deliveries = relationship("Delivery", back_populates="agent")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), unique=True, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="SET NULL"))
    status = Column(Enum(DeliveryStatus, native_enum=False), default=DeliveryStatus.pending, nullable=False)
    tracking_number = Column(String(50), unique=True)
    estimated_at = Column(DateTime(timezone=True))
    picked_at = Column(DateTime(timezone=True))
    in_transit_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    order = relationship("Order", back_populates="delivery", foreign_keys=[order_id])
    agent = relationship("DeliveryAgent", back_populates="deliveries")
    events = relationship("DeliveryEvent", back_populates="delivery", cascade="all, delete-orphan")


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(DeliveryStatus, native_enum=False), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_role = Column(Enum(ActorRole, native_enum=False), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    delivery = relationship("Delivery", back_populates="events")
    actor = relationship("User")


class PricingModel(str, enum.Enum):
    # Legacy. Fee derived from cart value alone — not monotonic (a cart crossing
    # 800 got CHEAPER delivery) and blind to distance. Kept only as a rollback.
    cart_total = "cart_total"
    # Distance bands + weight, one journey per cart. See delivery_pricing.py.
    cost_based = "cost_based"


class DeliveryRateSettings(Base):
    __tablename__ = "delivery_rate_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Which model checkout actually charges. Switch it from the admin Delivery
    # Rates page, after checking the change in the simulator.
    pricing_model = Column(String(20), nullable=False, default=PricingModel.cart_total.value)

    # Distance bands, cheapest to dearest. Read only by cost_based.
    #
    # Anchored in a3f81c26d945 to what buyers already pay. Across the 23 orders
    # that genuinely went through checkout, the legacy model charged an average
    # of Ksh 154, so same_county — the band every local order lands on until
    # sellers have wards on file — sits just under that at 130, keeping the
    # switch roughly price-neutral. Each band must stay >= the one above it: a
    # farther parcel may never cost less.
    same_ward_fee = Column(String(20), nullable=False, default="90.00")
    same_subcounty_fee = Column(String(20), nullable=False, default="110.00")
    same_county_fee = Column(String(20), nullable=False, default="130.00")
    same_region_fee = Column(String(20), nullable=False, default="190.00")
    adjacent_region_fee = Column(String(20), nullable=False, default="280.00")
    different_region_fee = Column(String(20), nullable=False, default="400.00")
    # Origin unplaceable, so priced as a regional trip rather than as a penalty
    # the buyer can't avoid.
    unknown_origin_fee = Column(String(20), nullable=False, default="190.00")

    # Weight surcharge, applied to cart weight above the free allowance. Only
    # products with a weight_kg actually set contribute (see parse_weight_kg).
    weight_allowance_kg = Column(String(20), nullable=False, default="10")
    per_kg_fee = Column(String(20), nullable=False, default="12.00")
    max_weight_surcharge = Column(String(20), nullable=False, default="600.00")

    # Bounds on the final cost_based quote. The floor keeps a tiny cart from
    # being delivered at a loss; the cap stops a heavy long-haul order from
    # quoting a fee no buyer would ever accept.
    min_delivery_fee = Column(String(20), nullable=False, default="60.00")
    max_delivery_fee = Column(String(20), nullable=False, default="800.00")

    # SLA window used to stamp Delivery.estimated_at when a delivery is assigned,
    # so the operations dashboard can compute an on-time-delivery rate.
    standard_delivery_hours = Column(Integer, nullable=False, default=48)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text)
    data = Column(JSONB)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")
