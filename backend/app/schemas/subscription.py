from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.subscription import SubscriptionStatus


class SubscriptionStatusResponse(BaseModel):
    status: SubscriptionStatus
    shop_slug: Optional[str] = None


class ResumePaymentRequest(BaseModel):
    reference: str


class ResumePaymentResponse(BaseModel):
    authorization_url: str
    reference: str


class SubscriptionPlanRead(BaseModel):
    code: str
    name: str
    price_monthly: str
    max_products: Optional[int]
    commission_rate: str

    model_config = {"from_attributes": True}


class SubscriptionRead(BaseModel):
    status: SubscriptionStatus
    plan: SubscriptionPlanRead
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]

    model_config = {"from_attributes": True}


class RenewSubscriptionResponse(BaseModel):
    authorization_url: str
    reference: str
