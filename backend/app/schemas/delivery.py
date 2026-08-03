import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.delivery import DeliveryStatus, DeliveryAgentStatus, ActorRole
from app.schemas.commerce import OrderRead


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


class DeliveryAgentListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[DeliveryAgentRead]


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
    order: Optional[OrderRead] = None

    model_config = {"from_attributes": True}


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus
    notes: Optional[str] = None


class DeliveryRateRead(BaseModel):
    id: uuid.UUID
    same_county_fee: str
    same_region_fee: str
    different_region_fee: str
    unknown_origin_fee: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeliveryRateUpdate(BaseModel):
    same_county_fee: Optional[str] = None
    same_region_fee: Optional[str] = None
    different_region_fee: Optional[str] = None
    unknown_origin_fee: Optional[str] = None
