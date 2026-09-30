import uuid
import enum
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
    # Photo proof URLs
    picked_photo_url: Optional[str] = None
    delivered_photo_url: Optional[str] = None
    created_at: datetime
    events: List[DeliveryEventRead] = []
    order: Optional[OrderRead] = None

    model_config = {"from_attributes": True}


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus
    notes: Optional[str] = None
    # Photo proof URLs (required for picked/delivered transitions)
    picked_photo_url: Optional[str] = None
    delivered_photo_url: Optional[str] = None


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
    # `raining=None` asks the API to live-check OpenWeather at the pickup
    # point; pass True/False to force the multiplier instead. Optional pickup
    # coordinates enable that auto-detection.
    raining: bool | None = None
    origin_lat: float | None = None
    origin_lng: float | None = None


class MeteredQuoteResponse(BaseModel):
    total: str
    currency: str
    breakdown: Dict[str, str | bool | float]


class DeliveryBatchStatus(str, enum.Enum):
    created = "created"
    assigned = "assigned"
    picked = "picked"
    in_transit = "in_transit"
    completed = "completed"
    cancelled = "cancelled"


class DeliveryBatchRead(BaseModel):
    id: uuid.UUID
    agent_id: Optional[uuid.UUID]
    status: DeliveryBatchStatus
    pickup_lat: Optional[float]
    pickup_lng: Optional[float]
    pickup_address: Optional[str]
    total_distance_km: Optional[float]
    estimated_duration_min: Optional[float]
    created_at: datetime
    assigned_at: Optional[datetime]
    picked_at: Optional[datetime]
    completed_at: Optional[datetime]
    deliveries: List[DeliveryRead] = []

    model_config = {"from_attributes": True}


class DeliveryBatchCreate(BaseModel):
    delivery_ids: List[uuid.UUID]  # deliveries to batch together


class DeliveryBatchAssign(BaseModel):
    agent_id: uuid.UUID


class DeliveryBatchStatusUpdate(BaseModel):
    status: DeliveryBatchStatus


# Safety Toolkit Schemas
class SafetyAlertType(str, enum.Enum):
    sos = "sos"
    check_in_missed = "check_in_missed"
    route_deviation = "route_deviation"
    speed_violation = "speed_violation"
    offline_too_long = "offline_too_long"


class SafetyAlertStatus(str, enum.Enum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"
    false_alarm = "false_alarm"


class SafetyAlertRead(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    delivery_id: Optional[uuid.UUID]
    alert_type: SafetyAlertType
    status: SafetyAlertStatus
    lat: Optional[float]
    lng: Optional[float]
    message: Optional[str]
    alert_metadata: Optional[dict]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[uuid.UUID]
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SafetyAlertCreate(BaseModel):
    alert_type: SafetyAlertType
    lat: Optional[float] = None
    lng: Optional[float] = None
    message: Optional[str] = None
    alert_metadata: Optional[dict] = None


class SafetyAlertAcknowledge(BaseModel):
    status: SafetyAlertStatus = SafetyAlertStatus.acknowledged


class EmergencyContactRead(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    phone: str
    contact_relationship: Optional[str]
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EmergencyContactCreate(BaseModel):
    name: str
    phone: str
    contact_relationship: Optional[str] = None
    is_primary: bool = False


class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    contact_relationship: Optional[str] = None
    is_primary: Optional[bool] = None


class TripShareRead(BaseModel):
    id: uuid.UUID
    delivery_id: uuid.UUID
    token: str
    expires_at: datetime
    created_at: datetime
    viewed_count: int
    last_viewed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TripShareCreate(BaseModel):
    delivery_id: uuid.UUID
    expires_in_hours: int = 24


# Loyalty / Gamification Schemas
class RiderTier(str, enum.Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    platinum = "platinum"


class QuestType(str, enum.Enum):
    delivery_count = "delivery_count"
    earnings_target = "earnings_target"
    streak_days = "streak_days"
    rating_target = "rating_target"
    peak_hours = "peak_hours"
    distance_total = "distance_total"
    referral = "referral"
    batch_complete = "batch_complete"


class QuestStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    claimed = "claimed"
    expired = "expired"
    cancelled = "cancelled"


class RewardType(str, enum.Enum):
    cash = "cash"
    bonus = "bonus"
    points = "points"
    badge = "badge"
    tier_upgrade = "tier_upgrade"


class QuestRead(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    quest_type: QuestType
    target_value: str
    reward_type: RewardType
    reward_value: str
    reward_badge: Optional[str]
    tier_requirement: Optional[RiderTier]
    is_active: bool
    is_recurring: bool
    recurrence_period: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestCreate(BaseModel):
    name: str
    description: Optional[str] = None
    quest_type: QuestType
    target_value: str
    reward_type: RewardType
    reward_value: str = "0"
    reward_badge: Optional[str] = None
    tier_requirement: Optional[RiderTier] = None
    is_active: bool = True
    is_recurring: bool = False
    recurrence_period: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class QuestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[str] = None
    reward_value: Optional[str] = None
    reward_badge: Optional[str] = None
    is_active: Optional[bool] = None
    is_recurring: Optional[bool] = None
    recurrence_period: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class QuestProgressRead(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    quest_id: uuid.UUID
    status: QuestStatus
    current_value: str
    completed_at: Optional[datetime]
    claimed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    quest: QuestRead

    model_config = {"from_attributes": True}


class RiderProfileRead(BaseModel):
    """Extended rider profile with loyalty info"""
    id: uuid.UUID
    name: str
    email: str
    phone: str
    tier: RiderTier
    loyalty_points: int
    lifetime_deliveries: int
    lifetime_earnings: str
    current_streak_days: int
    longest_streak_days: int
    last_active_date: Optional[datetime]
    total_distance_km: float
    rating_avg: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestProgressUpdate(BaseModel):
    """Update quest progress (internal use)"""
    current_value: str


# Dispatcher / SLA Schemas
class SLAConfigRead(BaseModel):
    id: uuid.UUID
    name: str
    max_dispatch_time_min: int
    max_pickup_time_min: int
    max_delivery_time_min: int
    max_total_time_min: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SLAConfigCreate(BaseModel):
    name: str
    max_dispatch_time_min: int = 30
    max_pickup_time_min: int = 60
    max_delivery_time_min: int = 120
    max_total_time_min: int = 180
    is_active: bool = True


class SLAConfigUpdate(BaseModel):
    name: Optional[str] = None
    max_dispatch_time_min: Optional[int] = None
    max_pickup_time_min: Optional[int] = None
    max_delivery_time_min: Optional[int] = None
    max_total_time_min: Optional[int] = None
    is_active: Optional[bool] = None


class SLABreachRead(BaseModel):
    id: uuid.UUID
    delivery_id: uuid.UUID
    breach_type: str
    expected_time: datetime
    actual_time: datetime
    breach_minutes: int
    severity: str
    is_alerted: bool
    alerted_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class DispatcherLogRead(BaseModel):
    id: uuid.UUID
    dispatcher_id: Optional[uuid.UUID]
    action: str
    delivery_id: Optional[uuid.UUID]
    agent_id: Optional[uuid.UUID]
    previous_agent_id: Optional[uuid.UUID]
    details: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ZoneConfigRead(BaseModel):
    id: uuid.UUID
    name: str
    boundary: dict
    center_lat: Optional[float]
    center_lng: Optional[float]
    radius_km: Optional[float]
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ZoneConfigCreate(BaseModel):
    name: str
    boundary: dict
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: Optional[float] = None
    is_active: bool = True
    priority: int = 0


class ZoneConfigUpdate(BaseModel):
    name: Optional[str] = None
    boundary: Optional[dict] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: Optional[float] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class AgentZoneAssignmentRead(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    zone_id: uuid.UUID
    is_primary: bool
    assigned_at: datetime
    assigned_by: Optional[uuid.UUID]
    zone: Optional[dict] = None

    model_config = {"from_attributes": True}


class AgentZoneAssignmentCreate(BaseModel):
    agent_id: uuid.UUID
    zone_id: uuid.UUID
    is_primary: bool = False


class DispatcherDashboardRead(BaseModel):
    active_agents: List[dict]
    active_deliveries: List[dict]
    pending_deliveries: List[dict]
    sla_breaches: List[SLABreachRead]
    zone_stats: List[dict]
    agent_locations: List[dict]
    updated_at: datetime

    model_config = {"from_attributes": True}


# Customer Tracking Schemas
class AgentLocationRead(BaseModel):
    """Real-time agent location for tracking"""
    agent_id: uuid.UUID
    name: str
    lat: Optional[float]
    lng: Optional[float]
    heading: Optional[float] = None
    speed_kmh: Optional[float] = None
    last_update: Optional[datetime]
    status: DeliveryAgentStatus

    model_config = {"from_attributes": True}


class DeliveryTrackingRead(BaseModel):
    """Complete delivery tracking info for customer"""
    delivery: DeliveryRead
    agent: Optional[AgentLocationRead] = None
    route: Optional[List[dict]] = None
    estimated_arrival: Optional[datetime]
    distance_remaining_km: Optional[float]
    status_display: str
    can_contact_agent: bool
    otp_required: bool
    otp_code: Optional[str] = None

    model_config = {"from_attributes": True}


class DeliveryOTPVerify(BaseModel):
    delivery_id: uuid.UUID
    otp_code: str
