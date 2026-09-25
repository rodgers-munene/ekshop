import uuid
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel
from app.models.delivery import DeliveryStatus, DeliveryAgentStatus, ActorRole, PricingModel
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
    current_order_id: Optional[uuid.UUID]
    total_deliveries: int
    weekly_earnings: str = "0.00"
    monthly_earnings: str = "0.00"
    rating_avg: str
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    last_location_update: Optional[datetime] = None
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
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    created_at: datetime
    events: List[DeliveryEventRead] = []
    order: Optional[OrderRead] = None

    model_config = {"from_attributes": True}


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus
    notes: Optional[str] = None


class DeliveryRateRead(BaseModel):
    id: uuid.UUID
    pricing_model: str
    same_ward_fee: str
    same_subcounty_fee: str
    same_county_fee: str
    same_region_fee: str
    adjacent_region_fee: str
    different_region_fee: str
    unknown_origin_fee: str
    weight_allowance_kg: str
    per_kg_fee: str
    max_weight_surcharge: str
    min_delivery_fee: str
    max_delivery_fee: str
    standard_delivery_hours: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeliveryRateUpdate(BaseModel):
    pricing_model: Optional[PricingModel] = None
    same_ward_fee: Optional[str] = None
    same_subcounty_fee: Optional[str] = None
    same_county_fee: Optional[str] = None
    same_region_fee: Optional[str] = None
    adjacent_region_fee: Optional[str] = None
    different_region_fee: Optional[str] = None
    unknown_origin_fee: Optional[str] = None
    weight_allowance_kg: Optional[str] = None
    per_kg_fee: Optional[str] = None
    max_weight_surcharge: Optional[str] = None
    min_delivery_fee: Optional[str] = None
    max_delivery_fee: Optional[str] = None
    standard_delivery_hours: Optional[int] = None


class DeliverySimulationRow(BaseModel):
    shop_id: uuid.UUID
    shop_name: str
    shop_county: Optional[str]
    region: Optional[str]
    cost_based_fees: Dict[str, str]   # buyer county -> cost_based fee from this shop
    cost_based_bands: Dict[str, str]  # buyer county -> which band that fee came from
    cart_total_fee: str


class DeliverySimulationResponse(BaseModel):
    buyer_counties: List[str]
    buyer_regions: Dict[str, Optional[str]]
    sample_cart_total: str
    sample_weight_kg: str
    live_model: str  # whichever PricingModel is actually charged today
    # The simulator only knows a buyer's county, so cost_based legs resolve no
    # finer than same_county — real checkouts with a ward set can land on the
    # cheaper same_ward/same_subcounty bands. Treat these as an upper bound.
    cost_based_resolution_note: str
    rows: List[DeliverySimulationRow]


class AgentStatusUpdate(BaseModel):
    status: DeliveryAgentStatus


class AgentLocationUpdate(BaseModel):
    lat: float
    lng: float


class DeliveryIssueCreate(BaseModel):
    reason: str
    notes: Optional[str] = None


class DeliveryIssueRead(BaseModel):
    id: uuid.UUID
    delivery_id: uuid.UUID
    reason: str
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RouteOptimizationRequest(BaseModel):
    delivery_ids: List[uuid.UUID]


class RouteOptimizationStop(BaseModel):
    delivery_id: uuid.UUID
    tracking_number: str
    buyer_name: str
    address: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    distance_from_previous_km: Optional[float] = None
    duration_from_previous_min: Optional[float] = None


class RouteOptimizationResponse(BaseModel):
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    total_distance_km: Optional[float] = None
    total_duration_min: Optional[float] = None
    stops: List[RouteOptimizationStop]
