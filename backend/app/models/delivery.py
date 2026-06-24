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
