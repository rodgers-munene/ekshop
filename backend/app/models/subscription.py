import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class SubscriptionStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    active = "active"
    cancelled = "cancelled"
    past_due = "past_due"
    trialing = "trialing"


class BillingInterval(str, enum.Enum):
    monthly = "monthly"
    annual = "annual"


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    price_monthly = Column(String(20), nullable=False)
    price_yearly = Column(String(20))
    max_products = Column(Integer)
    commission_rate = Column(String(10), nullable=False)
    features = Column(JSONB)
    is_active = Column(Boolean, default=True, nullable=False)

    subscriptions = relationship("Subscription", foreign_keys="Subscription.plan_id", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False)
    billing_interval = Column(
        Enum(BillingInterval, native_enum=False), default=BillingInterval.monthly, nullable=False
    )
    # Plan/interval a seller has picked but not yet paid for — applied by
    # activate_subscription() only once payment is confirmed, so an abandoned
    # checkout can't grant a higher plan's limits for free.
    pending_plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"))
    pending_billing_interval = Column(Enum(BillingInterval, native_enum=False))
    provider_ref = Column(String(100))
    customer_ref = Column(String(100))
    last_activated_ref = Column(String(100))
    status = Column(Enum(SubscriptionStatus, native_enum=False), default=SubscriptionStatus.trialing, nullable=False)
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    reminder_7d_sent_at = Column(DateTime(timezone=True))
    reminder_1d_sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    shop = relationship("Shop", back_populates="subscription")
    plan = relationship("SubscriptionPlan", foreign_keys=[plan_id], back_populates="subscriptions")
    pending_plan = relationship("SubscriptionPlan", foreign_keys=[pending_plan_id])

    @property
    def awaiting_first_payment(self) -> bool:
        """True for a subscription that has never had a real payment confirmed —
        either a pre-subscription-system shop backfilled straight to `active`
        with a 30-day window to pick a real plan (see migration
        f2a6c91b8d47), or (in principle) a `pending_payment`/`trialing`
        subscription. `status` alone can't distinguish this from a genuinely
        paid-up subscription, since the backfill sets status to `active`."""
        return self.last_activated_ref is None
