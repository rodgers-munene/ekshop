import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from app.models.payment import PaymentStatus


class PaymentInitiate(BaseModel):
    order_group_id: uuid.UUID
    provider: str
    amount: str
    currency: str = "KES"


class PaymentRead(BaseModel):
    id: uuid.UUID
    order_group_id: uuid.UUID
    provider: str
    provider_ref: Optional[str]
    amount: str
    currency: str
    status: PaymentStatus
    channel: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
