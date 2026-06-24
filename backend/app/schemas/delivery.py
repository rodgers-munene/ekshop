import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.delivery import DeliveryStatus


class DeliveryRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    agent_id: Optional[uuid.UUID]
    status: DeliveryStatus
    tracking_number: Optional[str]
    estimated_at: Optional[datetime]
    picked_at: Optional[datetime]
    in_transit_at: Optional[datetime]
    delivered_at: Optional[datetime]

    model_config = {"from_attributes": True}
