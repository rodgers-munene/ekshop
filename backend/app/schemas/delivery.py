import uuid
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel
from app.models.delivery import (
    DeliveryStatus,
    DeliveryAgentStatus,
    ActorRole,
    VehicleType,
    KYCStatus,
    OfferStatus,
    LedgerEntryType,
    LedgerStatus,
)
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
    same_county_fee: str
    same_region_fee: str
    different_region_fee: str
    unknown_origin_fee: str
    use_geo_pricing: bool
    standard_delivery_hours: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeliveryRateUpdate(BaseModel):
    same_county_fee: Optional[str] = None
    same_region_fee: Optional[str] = None
    different_region_fee: Optional[str] = None
    unknown_origin_fee: Optional[str] = None
    use_geo_pricing: Optional[bool] = None
    standard_delivery_hours: Optional[int] = None


class DeliverySimulationRow(BaseModel):
    shop_id: uuid.UUID
    shop_name: str
    shop_county: Optional[str]
    region: Optional[str]
    geo_fees: Dict[str, str]  # buyer county -> geo fee from this shop
    cart_total_fee: str


class DeliverySimulationResponse(BaseModel):
    buyer_counties: List[str]
    buyer_regions: Dict[str, Optional[str]]
    sample_cart_total: str
    live_model: str  # "geo" | "cart_total" — whichever is actually charged today
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


class KYCDocument(BaseModel):
    type: str
    url: str


class KYCSummaryBase(BaseModel):
    vehicle_type: Optional[VehicleType] = None
    national_id_number: Optional[str] = None
    license_number: Optional[str] = None


class KYCSummaryRead(KYCSummaryBase):
    id: uuid.UUID
    name: str
    email: str
    phone: str
    kyc_status: KYCStatus
    equipment_verified: bool
    kyc_review_notes: Optional[str] = None
    kyc_submitted_at: Optional[datetime] = None
    kyc_reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KYCDetailRead(KYCSummaryRead):
    kyc_documents: Optional[List[KYCDocument]] = None
    equipment_photo_url: Optional[str] = None
    wallet_balance: str = "0.00"
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    last_location_update: Optional[datetime] = None


class KYCSubmitRequest(BaseModel):
    vehicle_type: VehicleType
    national_id_number: str
    license_number: Optional[str] = None
    kyc_documents: Optional[List[KYCDocument]] = None
    equipment_photo_url: Optional[str] = None


class KYCReviewRequest(BaseModel):
    approve: bool
    notes: Optional[str] = None


class KYCAgentRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str
    kyc_status: KYCStatus
    vehicle_type: Optional[VehicleType] = None
    equipment_verified: bool
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    wallet_balance: str = "0.00"

    model_config = {"from_attributes": True}


class KYCAgentListResponse(BaseModel):
    total: int
    pending: int
    results: List[KYCAgentRead]


class OfferRead(BaseModel):
    id: uuid.UUID
    delivery_id: uuid.UUID
    status: OfferStatus
    queue_position: int
    expires_at: Optional[datetime] = None
    created_at: datetime
    delivery: Optional[DeliveryRead] = None

    model_config = {"from_attributes": True}


class OfferListResponse(BaseModel):
    offers: List[OfferRead]
    stale_expired: int = 0


class PingDispatchResponse(BaseModel):
    delivery_id: uuid.UUID
    offers_created: int
    offers: List[OfferRead]


class LedgerEntryRead(BaseModel):
    id: uuid.UUID
    delivery_id: Optional[uuid.UUID] = None
    entry_type: LedgerEntryType
    amount: str
    balance_after: str
    reference: Optional[str] = None
    status: LedgerStatus
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LedgerListResponse(BaseModel):
    agent_id: uuid.UUID
    wallet_balance: str
    entries: List[LedgerEntryRead]


class WalletTransactionRequest(BaseModel):
    amount: str
    note: Optional[str] = None


class PricingRuleUpsert(BaseModel):
    vehicle_type: VehicleType
    base_fare: str
    per_km_rate: str
    per_minute_rate: str = "0.00"
    rain_multiplier: str = "1.00"
    peak_hours_multiplier: str = "1.00"
    supply_demand_multiplier: str = "1.00"
    max_surge_cap: str = "2.00"
    currency: str = "KES"
    is_active: bool = True


class PricingRuleRead(BaseModel):
    id: uuid.UUID
    vehicle_type: VehicleType
    base_fare: str
    per_km_rate: str
    per_minute_rate: str
    rain_multiplier: str
    peak_hours_multiplier: str
    supply_demand_multiplier: str
    max_surge_cap: str
    currency: str
    is_active: bool

    model_config = {"from_attributes": True}


class PricingRuleListResponse(BaseModel):
    results: List[PricingRuleRead]


class MeteredQuoteRequest(BaseModel):
    distance_km: float
    duration_min: float = 0.0
    vehicle_type: VehicleType
    raining: bool = False


class MeteredQuoteResponse(BaseModel):
    total: str
    currency: str
    breakdown: Dict[str, str | bool | float]
