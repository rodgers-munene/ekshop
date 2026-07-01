import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.delivery import DeliveryStatus, DeliveryAgentStatus, ActorRole


class AgentLoginRequest(BaseModel):
    email: str
    password: str


class AgentTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DeliveryAgentCreate(BaseModel):
    name: str
    email: str
    phone: str
    password: str


class DeliveryAgentRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str
    status: DeliveryAgentStatus
    total_deliveries: int
    rating_avg: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliveryEventRead(BaseModel):
    id: uuid.UUID
    status: DeliveryStatus
    actor_role: ActorRole
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


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
    created_at: datetime
    events: List[DeliveryEventRead] = []

    model_config = {"from_attributes": True}


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus
    notes: Optional[str] = None
