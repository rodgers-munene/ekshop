from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.subscription import BillingInterval, SubscriptionStatus


class SubscriptionStatusResponse(BaseModel):
    status: SubscriptionStatus
    shop_slug: Optional[str] = None
    # Whether *this specific* payment reference has been applied — distinct from
    # `status == active`, which for an early renewal is already true beforehand.
    payment_confirmed: bool = False


class ResumePaymentRequest(BaseModel):
    reference: str


class ResumePaymentResponse(BaseModel):
    authorization_url: str
    reference: str


class SubscriptionPlanRead(BaseModel):
    code: str
    name: str
    price_monthly: str
    price_yearly: Optional[str]
    max_products: Optional[int]
    commission_rate: str

    model_config = {"from_attributes": True}


class SubscriptionRead(BaseModel):
    status: SubscriptionStatus
    plan: SubscriptionPlanRead
    billing_interval: BillingInterval
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    # True while `status` is active only because of the one-time backfill grace
    # window (or, in principle, before any payment has ever been confirmed) —
    # distinct from a subscription that's actually paid up.
    awaiting_first_payment: bool

    model_config = {"from_attributes": True}


class RenewSubscriptionRequest(BaseModel):
    # Omit both to renew the current plan/interval as-is (the simple retry
    # path). Set either to switch — applied only once payment confirms.
    plan_code: Optional[str] = None
    billing_interval: Optional[BillingInterval] = None


class RenewSubscriptionResponse(BaseModel):
    authorization_url: str
    reference: str
