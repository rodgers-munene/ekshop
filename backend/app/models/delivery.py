import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Integer, Boolean, Text, Float, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class DeliveryAgentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    busy = "busy"


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    assigned = "assigned"
    picked = "picked"
    in_transit = "in_transit"
    delivered = "delivered"
    cancelled = "cancelled"


class ActorRole(str, enum.Enum):
    customer = "customer"
    agent = "agent"
    admin = "admin"


class VehicleType(str, enum.Enum):
    bicycle = "bicycle"
    motorcycle = "motorcycle"
    pickup_van = "pickup_van"
    refrigerated_van = "refrigerated_van"
    refrigerated_truck = "refrigerated_truck"


class TemperatureRequirement(str, enum.Enum):
    ambient = "ambient"          # Room temperature (15-25°C)
    cool = "cool"                # Cool (2-8°C)
    frozen = "frozen"            # Frozen (-18°C or below)
    ultra_frozen = "ultra_frozen" # Ultra frozen (-40°C or below)


class VehicleRequirement(Base):
    """Defines vehicle requirements for different order types."""
    __tablename__ = "vehicle_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    required_vehicle_type = Column(Enum(VehicleType, native_enum=False), nullable=False)
    temperature_requirement = Column(Enum(TemperatureRequirement, native_enum=False), default=TemperatureRequirement.ambient)
    min_capacity_kg = Column(Integer, default=0)
    min_capacity_liters = Column(Integer, default=0)
    requires_license = Column(Boolean, default=False)
    license_type = Column(String(50))  # e.g., "Class C", "Hazmat"
    special_features = Column(JSONB)  # e.g., {"tail_lift": true, "gps_tracking": true}
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class KYCStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"


class OfferStatus(str, enum.Enum):
    queued = "queued"
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    cancelled = "cancelled"


class LedgerEntryType(str, enum.Enum):
    earning = "earning"
    b2c_payout = "b2c_payout"
    reversal = "reversal"
    adjustment = "adjustment"


class LedgerStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class RiderTier(str, enum.Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    platinum = "platinum"


class QuestType(str, enum.Enum):
    delivery_count = "delivery_count"      # Complete N deliveries
    earnings_target = "earnings_target"    # Earn KES X
    streak_days = "streak_days"            # Work N consecutive days
    rating_target = "rating_target"        # Maintain rating >= X
    peak_hours = "peak_hours"              # Deliver during peak hours
    distance_total = "distance_total"      # Cover X km total
    referral = "referral"                  # Refer a new rider
    batch_complete = "batch_complete"      # Complete a batch


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


class DeliveryAgent(Base):
    __tablename__ = "delivery_agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    password_hash = Column(String(255), nullable=False)
    status = Column(Enum(DeliveryAgentStatus, native_enum=False), default=DeliveryAgentStatus.active)
    current_order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"))
    total_deliveries = Column(Integer, default=0)
    rating_avg = Column(String(5), default="5.00")
    current_lat = Column(Float)
    current_lng = Column(Float)
    last_location_update = Column(DateTime(timezone=True))
    # Fleet-onboarding / KYC state
    vehicle_type = Column(Enum(VehicleType, native_enum=False))
    national_id_number = Column(String(50))
    license_number = Column(String(50))
    kyc_status = Column(Enum(KYCStatus, native_enum=False), default=KYCStatus.pending_review, nullable=False)
    kyc_documents = Column(JSONB)  # list of {type, url} KYC proof artifacts
    equipment_verified = Column(Boolean, default=False, nullable=False)
    equipment_photo_url = Column(String(500))
    kyc_submitted_at = Column(DateTime(timezone=True))
    kyc_reviewed_at = Column(DateTime(timezone=True))
    kyc_review_notes = Column(Text)
    # Wallet / payout ledger running balance. Writes happen ONLY through the
    # ledger service (credit/debit), never by direct column assignment.
    wallet_balance = Column(Numeric(14, 2), default=0, nullable=False)
    # Loyalty / Gamification
    tier = Column(Enum(RiderTier, native_enum=False), default=RiderTier.bronze, nullable=False)
    loyalty_points = Column(Integer, default=0, nullable=False)
    lifetime_deliveries = Column(Integer, default=0, nullable=False)
    lifetime_earnings = Column(Numeric(14, 2), default=0, nullable=False)
    current_streak_days = Column(Integer, default=0, nullable=False)
    longest_streak_days = Column(Integer, default=0, nullable=False)
    last_active_date = Column(DateTime(timezone=True), nullable=True)
    total_distance_km = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    current_order = relationship("Order", foreign_keys=[current_order_id])
    deliveries = relationship("Delivery", back_populates="agent")
    batches = relationship("DeliveryBatch", back_populates="agent")
    ledger_entries = relationship("DeliveryLedgerEntry", back_populates="agent", cascade="all, delete-orphan")
    safety_alerts = relationship("SafetyAlert", back_populates="agent", cascade="all, delete-orphan")
    emergency_contacts = relationship("EmergencyContact", back_populates="agent", cascade="all, delete-orphan")
    quest_progress = relationship("QuestProgress", back_populates="agent", cascade="all, delete-orphan")


class Quest(Base):
    """Quest/challenge definitions for rider gamification."""
    __tablename__ = "quests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    quest_type = Column(Enum(QuestType, native_enum=False), nullable=False)
    target_value = Column(Numeric(14, 2), nullable=False)  # e.g., 50 deliveries, 10000 KES, 7 days
    reward_type = Column(Enum(RewardType, native_enum=False), nullable=False)
    reward_value = Column(Numeric(14, 2), default=0, nullable=False)  # cash amount, points, etc.
    reward_badge = Column(String(100))  # badge identifier
    tier_requirement = Column(Enum(RiderTier, native_enum=False))  # minimum tier to access
    is_active = Column(Boolean, default=True, nullable=False)
    is_recurring = Column(Boolean, default=False, nullable=False)  # daily/weekly/monthly
    recurrence_period = Column(String(20))  # daily, weekly, monthly
    starts_at = Column(DateTime(timezone=True))
    ends_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    progress = relationship("QuestProgress", back_populates="quest", cascade="all, delete-orphan")


class QuestProgress(Base):
    """Tracks rider progress on a specific quest."""
    __tablename__ = "quest_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    quest_id = Column(UUID(as_uuid=True), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(QuestStatus, native_enum=False), default=QuestStatus.active, nullable=False)
    current_value = Column(Numeric(14, 2), default=0, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("agent_id", "quest_id", name="uq_quest_progress_agent_quest"),
    )

    agent = relationship("DeliveryAgent", back_populates="quest_progress")
    quest = relationship("Quest", back_populates="progress")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), unique=True, nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="SET NULL"))
    batch_id = Column(UUID(as_uuid=True), ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    status = Column(Enum(DeliveryStatus, native_enum=False), default=DeliveryStatus.pending, nullable=False)
    tracking_number = Column(String(50), unique=True)
    estimated_at = Column(DateTime(timezone=True))
    picked_at = Column(DateTime(timezone=True))
    in_transit_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    distance_km = Column(Float)
    duration_min = Column(Float)
    # Photo proof URLs (stored as S3/CDN URLs)
    picked_photo_url = Column(String(500))
    delivered_photo_url = Column(String(500))
    # OTP verification for delivery completion
    otp_code = Column(String(6))
    otp_expires_at = Column(DateTime(timezone=True))
    otp_verified_at = Column(DateTime(timezone=True))
    # Insurance
    insurance_enabled = Column(Boolean, default=False)
    insurance_value = Column(Numeric(14, 2), default=0)
    insurance_premium = Column(Numeric(14, 2), default=0)
    insurance_provider = Column(String(100))
    insurance_policy_number = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    order = relationship("Order", back_populates="delivery", foreign_keys=[order_id])
    agent = relationship("DeliveryAgent", back_populates="deliveries")
    batch = relationship("DeliveryBatch", back_populates="deliveries")
    events = relationship("DeliveryEvent", back_populates="delivery", cascade="all, delete-orphan")
    safety_alerts = relationship("SafetyAlert", back_populates="delivery")
    trip_shares = relationship("TripShare", back_populates="delivery", cascade="all, delete-orphan")
    stops = relationship("DeliveryStop", back_populates="delivery", cascade="all, delete-orphan", order_by="DeliveryStop.sequence")


class DeliveryStop(Base):
    """Individual stop in a multi-stop delivery."""
    __tablename__ = "delivery_stops"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)  # order of stops (1, 2, 3...)
    address = Column(JSONB, nullable=False)  # {first_name, last_name, phone, county, town, ward, exact_location, lat, lng}
    contact_name = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    status = Column(Enum(DeliveryStatus, native_enum=False), default=DeliveryStatus.pending, nullable=False)
    notes = Column(Text)
    estimated_at = Column(DateTime(timezone=True), nullable=True)
    arrived_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    photo_url = Column(String(500))
    otp_code = Column(String(6))
    otp_expires_at = Column(DateTime(timezone=True))
    otp_verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("delivery_id", "sequence", name="uq_delivery_stop_sequence"),
    )

    delivery = relationship("Delivery", back_populates="stops")


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(DeliveryStatus, native_enum=False), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_role = Column(Enum(ActorRole, native_enum=False), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    delivery = relationship("Delivery", back_populates="events")
    actor = relationship("User")


class DeliveryIssue(Base):
    __tablename__ = "delivery_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(100), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    delivery = relationship("Delivery")


class DeliveryBatchStatus(str, enum.Enum):
    created = "created"
    assigned = "assigned"
    picked = "picked"
    in_transit = "in_transit"
    completed = "completed"
    cancelled = "cancelled"


class DeliveryBatch(Base):
    """Batch multiple deliveries for a single rider pickup (same seller/area)."""
    __tablename__ = "delivery_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="SET NULL"))
    status = Column(Enum(DeliveryBatchStatus, native_enum=False), default=DeliveryBatchStatus.created, nullable=False)
    pickup_lat = Column(Float)
    pickup_lng = Column(Float)
    pickup_address = Column(Text)
    total_distance_km = Column(Float)
    estimated_duration_min = Column(Float)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    picked_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("DeliveryAgent", back_populates="batches")
    deliveries = relationship("Delivery", back_populates="batch")


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


class SafetyAlert(Base):
    """Safety alerts triggered by rider SOS, missed check-ins, or automated detection."""
    __tablename__ = "safety_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="SET NULL"))
    alert_type = Column(Enum(SafetyAlertType, native_enum=False), nullable=False)
    status = Column(Enum(SafetyAlertStatus, native_enum=False), default=SafetyAlertStatus.active, nullable=False)
    lat = Column(Float)
    lng = Column(Float)
    message = Column(Text)
    alert_metadata = Column(JSONB)  # additional context: speed, heading, battery, etc.
    triggered_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("DeliveryAgent", back_populates="safety_alerts")
    delivery = relationship("Delivery")


class EmergencyContact(Base):
    """Emergency contacts for riders."""
    __tablename__ = "emergency_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    contact_relationship = Column(String(50))  # spouse, parent, friend, etc.
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    agent = relationship("DeliveryAgent", back_populates="emergency_contacts")


class TripShare(Base):
    """Shareable trip links for real-time tracking by contacts."""
    __tablename__ = "trip_shares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    viewed_count = Column(Integer, default=0)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)

    delivery = relationship("Delivery")


class DeliveryRateSettings(Base):
    __tablename__ = "delivery_rate_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    same_county_fee = Column(String(20), nullable=False, default="200.00")
    same_region_fee = Column(String(20), nullable=False, default="350.00")
    different_region_fee = Column(String(20), nullable=False, default="600.00")
    unknown_origin_fee = Column(String(20), nullable=False, default="400.00")
    # Feature flag: while False, checkout keeps using the cart-total-tiered fee
    # (calculate_delivery_fee_from_cart_total). Flip to True once the county/region
    # model has been validated against real seller locations in the admin simulator.
    use_geo_pricing = Column(Boolean, nullable=False, default=False)
    # SLA window used to stamp Delivery.estimated_at when a delivery is assigned,
    # so the operations dashboard can compute an on-time-delivery rate.
    standard_delivery_hours = Column(Integer, nullable=False, default=48)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text)
    data = Column(JSONB)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")


class DeliveryOffer(Base):
    __tablename__ = "delivery_offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(OfferStatus, native_enum=False), default=OfferStatus.queued, nullable=False)
    queue_position = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    responded_at = Column(DateTime(timezone=True))

    delivery = relationship("Delivery")
    agent = relationship("DeliveryAgent")


class DeliveryPricingRule(Base):
    __tablename__ = "delivery_pricing_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_type = Column(Enum(VehicleType, native_enum=False), unique=True, nullable=False)
    base_fare = Column(Numeric(10, 2), nullable=False)
    per_km_rate = Column(Numeric(10, 2), nullable=False)
    per_minute_rate = Column(Numeric(10, 2), default=0, nullable=False)
    rain_multiplier = Column(Numeric(4, 2), default=1.00, nullable=False)
    peak_hours_multiplier = Column(Numeric(4, 2), default=1.00, nullable=False)
    supply_demand_multiplier = Column(Numeric(4, 2), default=1.00, nullable=False)
    max_surge_cap = Column(Numeric(4, 2), default=2.00, nullable=False)
    currency = Column(String(3), default="KES", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class DeliveryLedgerEntry(Base):
    __tablename__ = "delivery_ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="SET NULL"))
    entry_type = Column(Enum(LedgerEntryType, native_enum=False), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)  # signed: +credit, -debit
    balance_after = Column(Numeric(14, 2), nullable=False)
    reference = Column(String(100))
    status = Column(Enum(LedgerStatus, native_enum=False), default=LedgerStatus.pending, nullable=False)
    failure_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    agent = relationship("DeliveryAgent", back_populates="ledger_entries")
    delivery = relationship("Delivery")


class SLAConfig(Base):
    """SLA configuration for delivery time limits."""
    __tablename__ = "sla_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    max_dispatch_time_min = Column(Integer, default=30)
    max_pickup_time_min = Column(Integer, default=60)
    max_delivery_time_min = Column(Integer, default=120)
    max_total_time_min = Column(Integer, default=180)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SLABreach(Base):
    """Tracks SLA breaches for alerting and reporting."""
    __tablename__ = "sla_breaches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    breach_type = Column(String(50), nullable=False)
    expected_time = Column(DateTime(timezone=True), nullable=False)
    actual_time = Column(DateTime(timezone=True), nullable=False)
    breach_minutes = Column(Integer, nullable=False)
    severity = Column(String(20), default="medium")
    is_alerted = Column(Boolean, default=False)
    alerted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    delivery = relationship("Delivery")


class DispatcherLog(Base):
    __tablename__ = "dispatcher_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispatcher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(100), nullable=False)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="SET NULL"))
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="SET NULL"))
    previous_agent_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    delivery = relationship("Delivery")
    agent = relationship("DeliveryAgent")


class GPSFraudType(str, enum.Enum):
    gps_spoofing = "gps_spoofing"
    impossible_speed = "impossible_speed"
    teleportation = "teleportation"
    stationary_drift = "stationary_drift"
    route_deviation = "route_deviation"
    fake_delivery = "fake_delivery"
    location_mismatch = "location_mismatch"


class GPSFraudSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GPSFraudAlert(Base):
    """Detects and tracks GPS fraud/spoofing attempts by riders."""
    __tablename__ = "gps_fraud_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="SET NULL"))
    fraud_type = Column(Enum(GPSFraudType, native_enum=False), nullable=False)
    severity = Column(Enum(GPSFraudSeverity, native_enum=False), default=GPSFraudSeverity.medium, nullable=False)
    
    # Location data at time of detection
    lat = Column(Float)
    lng = Column(Float)
    speed_kmh = Column(Float)
    heading = Column(Float)
    accuracy_m = Column(Float)
    
    # Detection details
    expected_lat = Column(Float)
    expected_lng = Column(Float)
    distance_km = Column(Float)  # distance from expected location
    time_delta_sec = Column(Integer)  # time since last valid location
    speed_kmh = Column(Float)  # calculated speed
    
    # Evidence
    evidence = Column(JSONB)  # raw GPS points, timestamps, calculations
    description = Column(Text)
    
    # Status
    is_reviewed = Column(Boolean, default=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    resolution = Column(String(50))  # confirmed_fraud, false_positive, inconclusive
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    agent = relationship("DeliveryAgent")
    delivery = relationship("Delivery")


class ZoneConfig(Base):
    __tablename__ = "zone_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    boundary = Column(JSONB, nullable=False)
    center_lat = Column(Float)
    center_lng = Column(Float)
    radius_km = Column(Float)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AgentZoneAssignment(Base):
    __tablename__ = "agent_zone_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zone_configs.id", ondelete="CASCADE"), nullable=False)
    is_primary = Column(Boolean, default=False)
    assigned_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("agent_id", "zone_id", name="uq_agent_zone_assignment"),
    )

    agent = relationship("DeliveryAgent")
    zone = relationship("ZoneConfig")


class InsuranceClaimStatus(str, enum.Enum):
    filed = "filed"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    paid = "paid"
    closed = "closed"


class InsuranceClaimType(str, enum.Enum):
    damage = "damage"
    loss = "loss"
    theft = "theft"
    delay = "delay"


class InsuranceClaim(Base):
    """Insurance claims for delivery issues."""
    __tablename__ = "insurance_claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False)
    claimant_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # buyer or seller
    claim_type = Column(Enum(InsuranceClaimType, native_enum=False), nullable=False)
    status = Column(Enum(InsuranceClaimStatus, native_enum=False), default=InsuranceClaimStatus.filed, nullable=False)
    claimed_amount = Column(Numeric(14, 2), nullable=False)
    approved_amount = Column(Numeric(14, 2), default=0)
    description = Column(Text)
    evidence = Column(JSONB)  # photos, documents, etc.
    filed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    paid_at = Column(DateTime(timezone=True), nullable=True)

    delivery = relationship("Delivery")
    claimant = relationship("User")
