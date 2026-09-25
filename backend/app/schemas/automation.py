import uuid
from datetime import datetime

from pydantic import BaseModel


class AutomationSettingsRead(BaseModel):
    id: uuid.UUID
    webhook_url: str | None
    webhook_secret: str | None
    alert_min_gross_margin_pct: float
    alert_max_mpesa_latency_seconds: float
    alert_max_hosting_cost_per_order: float
    alert_max_order_cancellation_rate: float
    alert_min_on_time_delivery_rate: float
    alert_max_cart_abandonment_rate: float
    alert_gross_margin_enabled: bool
    alert_order_cancellation_enabled: bool
    alert_cart_abandonment_enabled: bool
    alert_on_time_delivery_enabled: bool
    daily_admin_report_enabled: bool
    daily_admin_report_email: str | None
    weekly_insight_digest_enabled: bool
    weekly_insight_digest_email: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class AutomationSettingsUpdate(BaseModel):
    webhook_url: str | None = None
    webhook_secret: str | None = None
    alert_min_gross_margin_pct: float | None = None
    alert_max_mpesa_latency_seconds: float | None = None
    alert_max_hosting_cost_per_order: float | None = None
    alert_max_order_cancellation_rate: float | None = None
    alert_min_on_time_delivery_rate: float | None = None
    alert_max_cart_abandonment_rate: float | None = None
    alert_gross_margin_enabled: bool | None = None
    alert_order_cancellation_enabled: bool | None = None
    alert_cart_abandonment_enabled: bool | None = None
    alert_on_time_delivery_enabled: bool | None = None
    daily_admin_report_enabled: bool | None = None
    daily_admin_report_email: str | None = None
    weekly_insight_digest_enabled: bool | None = None
    weekly_insight_digest_email: str | None = None
