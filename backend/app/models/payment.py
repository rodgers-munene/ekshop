import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    refunded = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_group_id = Column(UUID(as_uuid=True), ForeignKey("order_groups.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_ref = Column(String(100), unique=True)
    amount = Column(String(20), nullable=False)
    currency = Column(String(3), default="KES", nullable=False)
    status = Column(Enum(PaymentStatus, native_enum=False), default=PaymentStatus.pending, nullable=False)
    channel = Column(String(50))
    paid_at = Column(DateTime(timezone=True))
    raw_response = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    order_group = relationship("OrderGroup", back_populates="payments")
    user = relationship("User")


class PaymentIntent(Base):
    __tablename__ = "payment_intents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_group_id = Column(UUID(as_uuid=True), ForeignKey("order_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_ref = Column(String(100), unique=True)
    amount = Column(String(20), nullable=False)
    status = Column(Enum(PaymentStatus, native_enum=False), default=PaymentStatus.pending, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    order_group = relationship("OrderGroup", back_populates="payment_intents")
    user = relationship("User")
