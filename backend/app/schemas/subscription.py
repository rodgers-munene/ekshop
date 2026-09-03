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
