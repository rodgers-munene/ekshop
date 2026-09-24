from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class AutomationSettings(Base):
    __tablename__ = "automation_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_url = Column(String(512), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    alert_min_gross_margin_pct = Column(Float, nullable=False, default=90.0)
    alert_max_mpesa_latency_seconds = Column(Float, nullable=False, default=2.0)
    alert_max_hosting_cost_per_order = Column(Float, nullable=False, default=20.0)
    alert_max_order_cancellation_rate = Column(Float, nullable=False, default=10.0)
    alert_min_on_time_delivery_rate = Column(Float, nullable=False, default=80.0)
    alert_max_cart_abandonment_rate = Column(Float, nullable=False, default=70.0)
    daily_admin_report_enabled = Column(Boolean, nullable=False, default=True)
    daily_admin_report_email = Column(String(255), nullable=True)
    weekly_insight_digest_enabled = Column(Boolean, nullable=False, default=False)
    weekly_insight_digest_email = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
