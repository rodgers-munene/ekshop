import uuid
import secrets
import math
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.dependencies.auth import require_admin, get_current_active_user
from app.dependencies.database import get_db
from decimal import Decimal

from app.models.delivery import (
    DeliveryAgent, DeliveryAgentStatus, Delivery, DeliveryEvent, DeliveryIssue,
    DeliveryStatus, ActorRole, DeliveryOffer, DeliveryPricingRule, OfferStatus,
    DeliveryLedgerEntry, LedgerEntryType, LedgerStatus, VehicleType, KYCStatus,
    DeliveryBatch,
    SafetyAlert, SafetyAlertType, SafetyAlertStatus, EmergencyContact, TripShare,
    GPSFraudAlert, GPSFraudType, GPSFraudSeverity,
)
from app.models.commerce import Order, OrderStatus
from app.models.shop import Shop, ShopStatus
from app.models.user import User, UserRole
from app.schemas.delivery import (
    AgentLoginRequest, AgentTokenResponse,
    AgentStatusUpdate, AgentLocationUpdate,
    DeliveryAgentCreate, DeliveryAgentRead, DeliveryAgentListResponse,
    DeliveryIssueCreate, DeliveryIssueRead,
    DeliveryRead, DeliveryStatusUpdate,
    DeliveryRateRead, DeliveryRateUpdate,
    DeliverySimulationRow, DeliverySimulationResponse,
    RouteOptimizationRequest, RouteOptimizationResponse, RouteOptimizationStop,
    KYCDetailRead, KYCSubmitRequest, KYCReviewRequest,
    KYCAgentRead, KYCAgentListResponse,
    OfferRead, OfferListResponse, PingDispatchResponse,
    LedgerEntryRead, LedgerListResponse, WalletTransactionRequest,
    PricingRuleRead, PricingRuleListResponse, PricingRuleUpsert,
    MeteredQuoteRequest, MeteredQuoteResponse,
    DeliveryBatchRead, DeliveryBatchCreate, DeliveryBatchAssign,
    DeliveryBatchStatusUpdate, DeliveryBatchStatus,
    SafetyAlertRead, SafetyAlertCreate, SafetyAlertAcknowledge,
    EmergencyContactRead, EmergencyContactCreate, EmergencyContactUpdate,
    TripShareRead, TripShareCreate,
    DeliveryTrackingRead, AgentLocationRead,
    GPSFraudAlertRead, GPSFraudAlertListResponse, GPSFraudAlertReview,
)
from app.services.notifications import create_notification
from app.services.webhooks import emit_delivery_status_webhook
from app.services.delivery_pricing import (
    get_or_create_rate_settings,
    calculate_delivery_fee,
    calculate_delivery_fee_from_cart_total,
    get_region,
)
from app.services.routing import get_route_eta_distance, get_route_matrix
from app.services import fleet
from app.services.mpesa import get_access_token, initiate_b2c_payment, initiate_b2c_reversal

router = APIRouter(prefix="/delivery", tags=["delivery"])

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()

_agent_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired agent token",
    headers={"WWW-Authenticate": "Bearer"},
)

DELIVERY_TRANSITIONS = {
    "assigned":   ["picked", "cancelled"],
    "picked":     ["in_transit"],
    "in_transit": ["delivered"],
}

PERIOD_PATTERN = "^(today|yesterday|week|month)$"


def _period_bounds(period: Optional[str], days: int) -> tuple[datetime, datetime]:
    """Map a filter preset to a closed-open window [since, until) in Kenyan time."""
    from zoneinfo import ZoneInfo
    EAT = ZoneInfo("Africa/Nairobi")

    now = datetime.now(EAT)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period is None:
        return now - timedelta(days=days), now
    if period == "today":
        return today_start, now
    if period == "yesterday":
        return today_start - timedelta(days=1), today_start
    if period == "week":
        return now - timedelta(days=7), now
    return now - timedelta(days=30), now


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> DeliveryAgent:
    try:
        payload = decode_access_token(credentials.credentials)
        agent_id: str = payload.get("sub")
        if not agent_id or payload.get("type") != "agent":
            raise _agent_credentials_error
    except JWTError:
        raise _agent_credentials_error

    agent = db.query(DeliveryAgent).filter(DeliveryAgent.id == uuid.UUID(agent_id)).first()
    if not agent:
        raise _agent_credentials_error
    return agent


def _generate_tracking_number() -> str:
    return "EKS-" + secrets.token_hex(4).upper()


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=AgentTokenResponse)
def agent_login(payload: AgentLoginRequest, db: Session = Depends(get_db)):
    agent = db.query(DeliveryAgent).filter(DeliveryAgent.email == payload.email).first()
    if not agent or not verify_password(payload.password, agent.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = create_access_token(
        {"sub": str(agent.id)},
        expires_delta=timedelta(hours=12),
        token_type="agent",
    )
    return AgentTokenResponse(access_token=token)


# ── Admin: manage agents ──────────────────────────────────────────────────────

@router.post("/agents", response_model=DeliveryAgentRead, status_code=201)
def create_agent(
    payload: DeliveryAgentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = db.query(DeliveryAgent).filter(DeliveryAgent.email == payload.email).first()
    if existing:
        raise HTTPException(409, "An agent with this email already exists")

    agent = DeliveryAgent(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents", response_model=DeliveryAgentListResponse)
def list_agents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(DeliveryAgent)
    total = query.count()
    skip = (page - 1) * limit
    results = query.order_by(DeliveryAgent.created_at.desc()).offset(skip).limit(limit).all()
    return DeliveryAgentListResponse(total=total, page=page, limit=limit, results=results)


# ── Admin: assign delivery ────────────────────────────────────────────────────

@router.post("/{order_id}/assign", response_model=DeliveryRead, status_code=201)
async def assign_delivery(
    order_id: uuid.UUID,
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")

    if order.status not in (OrderStatus.confirmed, OrderStatus.processing):
        raise HTTPException(400, f"Cannot assign delivery for order in '{order.status}' status")

    agent = db.query(DeliveryAgent).filter(DeliveryAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status == DeliveryAgentStatus.inactive:
        raise HTTPException(400, "Agent is inactive")
    if agent.kyc_status != KYCStatus.approved:
        raise HTTPException(400, "Rider KYC is not approved; cannot assign deliveries")
    if not agent.equipment_verified:
        raise HTTPException(400, "Rider equipment is not verified; cannot assign deliveries")

    delivery = db.query(Delivery).filter(Delivery.order_id == order_id).first()
    if not delivery:
        delivery = Delivery(
            order_id=order_id,
            tracking_number=_generate_tracking_number(),
        )
        db.add(delivery)
        db.flush()

    if delivery.status not in (DeliveryStatus.pending, DeliveryStatus.assigned):
        raise HTTPException(400, f"Delivery already in '{delivery.status}' status")

    # Reassigning: free the earlier rider, who must not stay silently busy on a
    # delivery they no longer carry.
    if delivery.agent_id is not None and delivery.agent_id != agent_id:
        prev_agent = db.get(DeliveryAgent, delivery.agent_id)
        if prev_agent is not None and prev_agent.current_order_id == order_id:
            prev_agent.current_order_id = None
            prev_agent.status = DeliveryAgentStatus.active

    delivery.agent_id = agent_id
    delivery.status = DeliveryStatus.assigned
    if not delivery.estimated_at:
        sla_hours = get_or_create_rate_settings(db).standard_delivery_hours
        delivery.estimated_at = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

    # Manual assign wins over any open ping window: close sibling offers so no
    # rider can accept or extend the wait chain for an already-claimed delivery.
    fleet.cancel_open_offers(db, delivery.id)

    if delivery.distance_km is None and order.shop and order.delivery_address:
        shop = order.shop
        address = order.delivery_address
        if shop.lat and shop.lng and address.lat and address.lng:
            route = await get_route_eta_distance(shop.lat, shop.lng, address.lat, address.lng)
            if route["distance_km"] is not None:
                delivery.distance_km = route["distance_km"]
                delivery.duration_min = route["duration_min"]

    event = DeliveryEvent(
        delivery_id=delivery.id,
        status=DeliveryStatus.assigned,
        updated_by=admin.id,
        actor_role=ActorRole.admin,
        notes=f"Assigned to agent {agent.name}",
    )
    db.add(event)

    agent.status = DeliveryAgentStatus.busy
    agent.current_order_id = order_id

    create_notification(
        db,
        user_id=order.buyer_id,
        type="delivery_status",
        title="Delivery assigned",
        body=f"A delivery agent has been assigned to your order. Tracking: {delivery.tracking_number}.",
        data={"delivery_id": str(delivery.id), "tracking_number": delivery.tracking_number},
    )

    db.commit()
    db.refresh(delivery)

    await emit_delivery_status_webhook(str(delivery.id), "assigned", str(delivery.order_id))
    return delivery


# ── Agent: update delivery status ─────────────────────────────────────────────

@router.patch("/{delivery_id}/status", response_model=DeliveryRead)
async def update_delivery_status(
    delivery_id: uuid.UUID,
    payload: DeliveryStatusUpdate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.agent_id == agent.id,
    ).first()
    if not delivery:
        raise HTTPException(404, "Delivery not found")

    allowed = DELIVERY_TRANSITIONS.get(delivery.status, [])
    if payload.status not in allowed:
        raise HTTPException(400, f"Cannot transition from '{delivery.status}' to '{payload.status}'")

    # Validate photo proof requirements
    if payload.status == DeliveryStatus.picked:
        if not payload.picked_photo_url:
            raise HTTPException(400, "Photo proof is required when marking order as picked up")
    if payload.status == DeliveryStatus.delivered:
        if not payload.delivered_photo_url:
            raise HTTPException(400, "Photo proof is required when marking order as delivered")

    now = datetime.now(timezone.utc)
    delivery.status = payload.status

    if payload.status == DeliveryStatus.picked:
        delivery.picked_at = now
        delivery.picked_photo_url = payload.picked_photo_url
    elif payload.status == DeliveryStatus.in_transit:
        delivery.in_transit_at = now
    elif payload.status == DeliveryStatus.delivered:
        address = delivery.order.delivery_address or {}
        buyer_lat = address.get("lat")
        buyer_lng = address.get("lng")
        if buyer_lat and buyer_lng and agent.current_lat and agent.current_lng:
            distance = _haversine(agent.current_lat, agent.current_lng, float(buyer_lat), float(buyer_lng))
            if distance > 0.5:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"You must be within 500m of the delivery address to mark as delivered. Current distance: {distance:.2f} km",
                )
        delivery.delivered_at = now
        delivery.delivered_photo_url = payload.delivered_photo_url
        agent.total_deliveries += 1
        agent.status = DeliveryAgentStatus.active
        agent.current_order_id = None
        # rider's share of the delivery fee lands in the wallet ledger
        fleet.credit_delivery_earnings(db, delivery, agent)

    event = DeliveryEvent(
        delivery_id=delivery.id,
        status=payload.status,
        actor_role=ActorRole.agent,
        notes=payload.notes,
    )
    db.add(event)

    create_notification(
        db,
        user_id=delivery.order.buyer_id,
        type="delivery_status",
        title="Delivery update",
        body=f"Your delivery is now '{payload.status.value}'.",
        data={"delivery_id": str(delivery.id), "status": payload.status.value},
    )

    db.commit()
    db.refresh(delivery)

    await emit_delivery_status_webhook(str(delivery.id), payload.status.value, str(delivery.order_id))
    return delivery


# ── Agent: my deliveries ──────────────────────────────────────────────────────

@router.get("/agents/me", response_model=DeliveryAgentRead)
def my_agent_profile(agent: DeliveryAgent = Depends(get_current_agent)):
    return agent


@router.get("/me", response_model=List[DeliveryRead])
def my_deliveries(
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    return (
        db.query(Delivery)
        .options(
            selectinload(Delivery.order).selectinload(Order.buyer),
            selectinload(Delivery.order).selectinload(Order.items),
            selectinload(Delivery.order).selectinload(Order.shop),
        )
        .filter(Delivery.agent_id == agent.id)
        .order_by(Delivery.created_at.desc())
        .all()
    )


@router.patch("/agents/me/status", response_model=DeliveryAgentRead)
def update_my_status(
    payload: AgentStatusUpdate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    # A rider may only come online after an admin has approved their KYC and
    # vehicle/equipment verification — the fleet safety gate.
    if payload.status == DeliveryAgentStatus.active:
        if agent.kyc_status != KYCStatus.approved:
            raise HTTPException(400, "KYC not approved yet. Complete onboarding before going online.")
        if not agent.equipment_verified:
            raise HTTPException(400, "Equipment verification pending. Complete onboarding before going online.")
        if not agent.current_lat or not agent.current_lng:
            raise HTTPException(400, "Location not set. Share your location before going online.")

    agent.status = payload.status
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents/me/status", response_model=DeliveryAgentRead)
def get_my_status(
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    return agent


@router.patch("/agents/me/location", response_model=DeliveryAgentRead)
def update_my_location(
    payload: AgentLocationUpdate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    agent.current_lat = payload.lat
    agent.current_lng = payload.lng
    agent.last_location_update = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents/locations")
def get_agent_locations(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    agents = (
        db.query(DeliveryAgent)
        .filter(DeliveryAgent.current_lat.is_not(None), DeliveryAgent.current_lng.is_not(None))
        .all()
    )
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "status": a.status.value,
            "lat": a.current_lat,
            "lng": a.current_lng,
            "last_update": a.last_location_update.isoformat() if a.last_location_update else None,
            "current_order_id": str(a.current_order_id) if a.current_order_id else None,
        }
        for a in agents
    ]


@router.get("/agents/me/earnings")
def my_earnings(
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    weekly = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.agent_id == agent.id,
            Delivery.status == DeliveryStatus.delivered,
            Delivery.delivered_at >= week_start,
        )
        .scalar()
        or 0
    )
    monthly = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.agent_id == agent.id,
            Delivery.status == DeliveryStatus.delivered,
            Delivery.delivered_at >= month_start,
        )
        .scalar()
        or 0
    )

    # Earnings come from the wallet ledger now: the rider's share of the
    # delivery fee is credited on delivery and any B2C payout debits it.
    # Response shape is kept identical for the rider PWA.
    def _earning_sum(since: datetime) -> Decimal:
        total = (
            db.query(func.sum(DeliveryLedgerEntry.amount))
            .filter(
                DeliveryLedgerEntry.agent_id == agent.id,
                DeliveryLedgerEntry.entry_type == LedgerEntryType.earning,
                DeliveryLedgerEntry.created_at >= since,
            )
            .scalar()
        )
        return Decimal(total or 0)

    weekly_earnings = _earning_sum(week_start)
    monthly_earnings = _earning_sum(month_start)

    return {
        "total_deliveries": agent.total_deliveries,
        "weekly_deliveries": weekly,
        "monthly_deliveries": monthly,
        "weekly_earnings": str(weekly_earnings),
        "monthly_earnings": str(monthly_earnings),
        "wallet_balance": str(agent.wallet_balance or Decimal("0.00")),
    }


@router.get("/pricing-rules", response_model=PricingRuleListResponse)
def list_pricing_rules(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rules = db.query(DeliveryPricingRule).order_by(DeliveryPricingRule.vehicle_type).all()
    return PricingRuleListResponse(results=rules)


@router.post("/{delivery_id}/issue", response_model=DeliveryIssueRead, status_code=status.HTTP_201_CREATED)
def report_delivery_issue(
    delivery_id: uuid.UUID,
    payload: DeliveryIssueCreate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id, Delivery.agent_id == agent.id).first()
    if not delivery:
        raise HTTPException(404, "Delivery not found")

    issue = DeliveryIssue(
        delivery_id=delivery_id,
        reason=payload.reason,
        notes=payload.notes,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.post("/optimize-route", response_model=RouteOptimizationResponse)
async def optimize_route(
    payload: RouteOptimizationRequest,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    deliveries = (
        db.query(Delivery)
        .options(selectinload(Delivery.order).selectinload(Order.shop))
        .filter(Delivery.id.in_(payload.delivery_ids), Delivery.agent_id == agent.id)
        .all()
    )
    if not deliveries:
        raise HTTPException(404, "No deliveries found")

    stops: List[RouteOptimizationStop] = []
    coords: List[tuple[float, float]] = []
    for d in deliveries:
        addr = d.order.delivery_address or {}
        lat = addr.get("lat")
        lng = addr.get("lng")
        stop = RouteOptimizationStop(
            delivery_id=d.id,
            tracking_number=d.tracking_number or "",
            buyer_name=d.order.buyer.name if d.order and d.order.buyer else "Customer",
            address=f"{addr.get('exact_location') or addr.get('town') or ''}, {addr.get('county') or ''}".strip(", "),
            lat=float(lat) if lat else None,
            lng=float(lng) if lng else None,
        )
        stops.append(stop)
        if lat and lng:
            coords.append((float(lat), float(lng)))

    if len(coords) < 2:
        return RouteOptimizationResponse(stops=stops)

    try:
        matrix = await get_route_matrix(coords)
    except Exception:
        logger.warning("Route matrix unavailable, falling back to haversine", exc_info=True)
        matrix = [[0.0 if i == j else _haversine(*coords[i], *coords[j]) for j in range(len(coords))] for i in range(len(coords))]

    def leg_values(i: int, j: int) -> tuple[float, float | None]:
        leg = matrix[i][j]
        if isinstance(leg, dict):
            dist = leg.get("distance_km")
            dur = leg.get("duration_min")
            if dist is None:
                dist = _haversine(*coords[i], *coords[j])
            return float(dist), (float(dur) if dur is not None else None)
        return float(leg), None

    unvisited = set(range(len(coords)))
    path = [0]
    unvisited.discard(0)
    total_dist = 0.0
    total_dur = 0.0

    while unvisited:
        last = path[-1]
        next_idx = min(unvisited, key=lambda i: leg_values(last, i)[0])
        dist, dur = leg_values(last, next_idx)
        total_dist += dist
        if dur is not None:
            total_dur += dur
        stops[next_idx].distance_from_previous_km = round(dist, 2)
        stops[next_idx].duration_from_previous_min = round(dur, 2) if dur is not None else None
        path.append(next_idx)
        unvisited.discard(next_idx)

    ordered = [stops[i] for i in path]
    return RouteOptimizationResponse(
        origin_lat=coords[0][0] if coords else None,
        origin_lng=coords[0][1] if coords else None,
        total_distance_km=round(total_dist, 2),
        total_duration_min=round(total_dur, 2) if total_dur else None,
        stops=ordered,
    )


# ── Admin: delivery fee rates ──────────────────────────────────────────────────

@router.get("/rates", response_model=DeliveryRateRead)
def get_delivery_rates(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    settings = get_or_create_rate_settings(db)
    db.commit()
    db.refresh(settings)
    return settings


@router.put("/rates", response_model=DeliveryRateRead)
def update_delivery_rates(
    payload: DeliveryRateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    settings = get_or_create_rate_settings(db)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return settings


# ── Admin: simulate geo pricing against real seller locations ─────────────────

@router.get("/simulate", response_model=DeliverySimulationResponse)
def simulate_delivery_fees(
    buyer_county: List[str] = Query(..., description="One or more counties to simulate a buyer ordering from"),
    sample_cart_total: Decimal = Query(Decimal("500"), ge=0, description="Cart total to compare against the legacy tiered model"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    settings = get_or_create_rate_settings(db)
    db.commit()

    shops = (
        db.query(Shop)
        .filter(Shop.status == ShopStatus.active)
        .order_by(Shop.name)
        .all()
    )

    cart_total_fee = calculate_delivery_fee_from_cart_total(sample_cart_total)

    rows = [
        DeliverySimulationRow(
            shop_id=shop.id,
            shop_name=shop.name,
            shop_county=shop.county,
            region=get_region(shop.county),
            geo_fees={
                county: str(calculate_delivery_fee(county, shop.county, settings))
                for county in buyer_county
            },
            cart_total_fee=str(cart_total_fee),
        )
        for shop in shops
    ]

    return DeliverySimulationResponse(
        buyer_counties=buyer_county,
        buyer_regions={county: get_region(county) for county in buyer_county},
        sample_cart_total=str(sample_cart_total),
        live_model="geo" if settings.use_geo_pricing else "cart_total",
        rows=rows,
    )


# ── Fleet: rider KYC + vehicle/equipment verification ────────────────────────

@router.get("/kyc/me", response_model=KYCDetailRead)
def my_kyc(
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    return agent


@router.put("/kyc/me", response_model=KYCDetailRead)
def submit_kyc(
    payload: KYCSubmitRequest,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    agent.vehicle_type = payload.vehicle_type
    agent.national_id_number = payload.national_id_number
    agent.license_number = payload.license_number
    agent.kyc_documents = [doc.model_dump() for doc in payload.kyc_documents] if payload.kyc_documents else None
    agent.equipment_photo_url = payload.equipment_photo_url
    agent.kyc_status = KYCStatus.pending_review
    agent.kyc_submitted_at = datetime.now(timezone.utc)
    agent.kyc_reviewed_at = None
    agent.kyc_review_notes = None
    # a re-flight off the road until re-approved
    agent.status = DeliveryAgentStatus.inactive
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/admin/kyc", response_model=KYCAgentListResponse)
def kyc_queue(
    status_filter: KYCStatus = Query(KYCStatus.pending_review, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(DeliveryAgent).filter(DeliveryAgent.kyc_status == status_filter)
    pending = (
        db.query(func.count(DeliveryAgent.id))
        .filter(DeliveryAgent.kyc_status == KYCStatus.pending_review)
        .scalar()
        or 0
    )
    results = query.order_by(DeliveryAgent.kyc_submitted_at.asc().nullslast()).all()
    return KYCAgentListResponse(total=len(results), pending=pending, results=results)


@router.post("/admin/kyc/{agent_id}/approve", response_model=KYCAgentRead)
def approve_kyc(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    agent = db.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.kyc_status = KYCStatus.approved
    agent.equipment_verified = True
    agent.kyc_reviewed_at = datetime.now(timezone.utc)
    agent.kyc_review_notes = "Approved by admin"
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/admin/kyc/{agent_id}/reject", response_model=KYCAgentRead)
def reject_kyc(
    agent_id: uuid.UUID,
    payload: KYCReviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    agent = db.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.kyc_status = KYCStatus.rejected
    agent.equipment_verified = False
    agent.kyc_reviewed_at = datetime.now(timezone.utc)
    agent.kyc_review_notes = payload.notes or "Rejected by admin"
    agent.status = DeliveryAgentStatus.inactive
    db.commit()
    db.refresh(agent)
    return agent


# ── Fleet: automated ping dispatch engine ─────────────────────────────────────

@router.post("/{order_id}/dispatch", response_model=PingDispatchResponse)
def dispatch_delivery(
    order_id: uuid.UUID,
    radius_km: float = Query(None, ge=0.1, le=100),
    expires_seconds: int = Query(None, ge=10, le=300),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    delivery = db.query(Delivery).filter(Delivery.order_id == order_id).first()
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    if delivery.status != DeliveryStatus.pending:
        raise HTTPException(400, f"Delivery is in '{delivery.status.value}' status; only pending deliveries can be dispatched")

    offers = fleet.dispatch(db, delivery, radius_km=radius_km, expires_after_seconds=expires_seconds)
    db.commit()
    return PingDispatchResponse(
        delivery_id=delivery.id,
        offers_created=len(offers),
        offers=offers,
    )


@router.get("/offers/me", response_model=OfferListResponse)
def my_offers(
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    # lazily expire overdue pings before listing so riders see live offers only
    stale = fleet.expire_stale_offers(db)
    db.commit()

    offers = (
        db.query(DeliveryOffer)
        .options(selectinload(DeliveryOffer.delivery))
        .filter(DeliveryOffer.agent_id == agent.id)
        .filter(DeliveryOffer.status.in_([OfferStatus.pending, OfferStatus.queued]))
        .order_by(DeliveryOffer.created_at.desc())
        .all()
    )
    return OfferListResponse(offers=offers, stale_expired=stale)


@router.post("/offers/{offer_id}/accept", response_model=DeliveryRead)
def accept_ping(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    offer = db.get(DeliveryOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Ping not found")
    # re-check expiry before accepting
    fleet.expire_stale_offers(db)
    db.refresh(offer)
    try:
        delivery = fleet.accept_offer(db, offer, agent)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    db.commit()
    db.refresh(delivery)
    return delivery


@router.post("/offers/{offer_id}/decline", response_model=OfferRead)
def decline_ping(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    offer = db.get(DeliveryOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Ping not found")
    try:
        declined = fleet.decline_offer(db, offer, agent)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc))
    db.commit()
    db.refresh(declined)
    return declined


@router.post("/offers/expire-stale", response_model=int)
def expire_stale_pings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    count = fleet.expire_stale_offers(db)
    db.commit()
    return count


# ── Fleet: wallet ledger + B2C payouts + reversal ─────────────────────────────

@router.get("/agents/me/ledger", response_model=LedgerListResponse)
def my_ledger(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    entries = (
        db.query(DeliveryLedgerEntry)
        .filter(DeliveryLedgerEntry.agent_id == agent.id)
        .order_by(DeliveryLedgerEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    return LedgerListResponse(agent_id=agent.id, wallet_balance=str(agent.wallet_balance or Decimal("0.00")), entries=entries)


@router.get("/admin/ledger", response_model=LedgerListResponse)
def admin_ledger(
    agent_id: uuid.UUID,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    agent = db.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    entries = (
        db.query(DeliveryLedgerEntry)
        .filter(DeliveryLedgerEntry.agent_id == agent_id)
        .order_by(DeliveryLedgerEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    return LedgerListResponse(agent_id=agent_id, wallet_balance=str(agent.wallet_balance or Decimal("0.00")), entries=entries)


@router.post("/admin/ledger/{agent_id}/payout", response_model=LedgerEntryRead)
async def trigger_b2c_payout(
    agent_id: uuid.UUID,
    payload: WalletTransactionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin-triggered B2C payout of part of a rider's wallet balance to their
    M-Pesa number. The wallet debit is provisional (pending) until Daraja's
    Result callback (/payments/b2c/callback) settles it — ResponseCode 0 at
    initiation only means the request was QUEUED, not that the money moved."""
    agent = db.get(DeliveryAgent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    try:
        amount = Decimal(payload.amount)
    except Exception:
        raise HTTPException(400, "amount must be a valid decimal")

    balance = Decimal(agent.wallet_balance or 0)
    if amount <= 0:
        raise HTTPException(400, "amount must be greater than zero")
    if amount > balance:
        raise HTTPException(400, f"Cannot payout {amount}; wallet balance is {balance}")

    entry = fleet.create_manual_payout(db, agent, amount)
    db.commit()

    try:
        token = get_access_token()
        phone = agent.phone
        response = initiate_b2c_payment(
            token,
            phone,
            int(amount),
            remarks=payload.note or "Rider payout",
            transaction_id=str(entry.id),
        )
        response_code = response.get("ResponseCode")
        queued = response_code in ("0", 0)
        originator = response.get("OriginatorConversationID") or str(entry.id)
        if queued:
            # Accepted and queued — keep the entry PENDING and record the
            # OriginatorConversationID so the Result callback can reconcile it.
            fleet.mark_payout_queued(db, entry, reference=originator)
            db.commit()
        else:
            fleet.mark_payout_result(
                db, entry, reference=originator, succeeded=False,
                failure_reason=f"M-Pesa ResponseCode {response_code}",
            )
            db.commit()
    except Exception as exc:
        logger.warning("B2C payout initiation failed for %s", agent.id, exc_info=True)
        fleet.mark_payout_result(
            db, entry, reference=None, succeeded=False, failure_reason=str(exc)
        )
        db.commit()
        raise HTTPException(502, f"B2C payout initiation failed: {exc}")
    db.refresh(entry)
    return entry


@router.post("/admin/ledger/{entry_id}/reverse", response_model=LedgerEntryRead)
async def reverse_payout(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Reverses a previously-fulfilled B2C payout back into the rider's wallet.
    Side effect on M-Pesa is best-effort: reversal is posted to the ledger
    regardless so the wallet stays consistent."""
    entry = db.get(DeliveryLedgerEntry, entry_id)
    if not entry:
        raise HTTPException(404, "Ledger entry not found")
    if entry.entry_type != LedgerEntryType.b2c_payout or entry.status != LedgerStatus.succeeded:
        raise HTTPException(400, "Only a succeeded B2C payout can be reversed")

    agent = entry.agent
    try:
        token = get_access_token()
        initiate_b2c_reversal(token, transaction_id=entry.reference or str(entry.id), amount=abs(int(entry.amount)))
    except Exception as exc:
        logger.warning("B2C reversal failed for ledger %s (%s)", entry.id, exc)

    fleet.post_ledger_entry(
        db, agent, LedgerEntryType.reversal, -entry.amount,
        delivery_id=entry.delivery_id, reference=f"reversal-of-{entry.id}",
    )
    db.commit()
    db.refresh(entry)
    return entry


# ── Fleet: metered pricing rules + quote ──────────────────────────────────────

@router.put("/pricing-rules/{vehicle_type}", response_model=PricingRuleRead)
def upsert_pricing_rule(
    vehicle_type: VehicleType,
    payload: PricingRuleUpsert,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rule = db.query(DeliveryPricingRule).filter(DeliveryPricingRule.vehicle_type == vehicle_type).first()
    if rule is None:
        rule = DeliveryPricingRule(vehicle_type=vehicle_type)
        db.add(rule)

    for field, value in payload.model_dump(exclude={"vehicle_type"}).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.post("/quote", response_model=MeteredQuoteResponse)
async def metered_quote(
    payload: MeteredQuoteRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Quote production pricing for a delivery. As a design choice the quote
    accepts explicit distance/duration so the router doesn't depend on a live
    routing provider at request time; pass values already computed by ORS or
    the legacy cart-total path as needed. Returns the surge-affected metered
    total plus the full breakdown."""
    rule = fleet.get_pricing_rule(db, payload.vehicle_type)
    if rule is None:
        return MeteredQuoteResponse(
            total="0.00",
            currency="KES",
            breakdown={
                "base_fare": "0.00",
                "per_km": "0.00",
                "per_minute": "0.00",
                "surge_multiplier": "1.00",
                "peak_hours": False,
                "raining": False,
                "rain_multiplier": "1.00",
                "peak_hours_multiplier": "1.00",
                "supply_demand_multiplier": "1.00",
                "currency": "KES",
            },
        )

    raining = payload.raining
    if raining is None:
        raining = False
        if payload.origin_lat is not None and payload.origin_lng is not None:
            detected = await fleet.fetch_raining(payload.origin_lat, payload.origin_lng)
            if detected is not None:
                raining = detected

    total, breakdown = fleet.calculate_metered_fee(
        distance_km=payload.distance_km,
        duration_min=payload.duration_min,
        vehicle_type=payload.vehicle_type,
        rule=rule,
        raining=raining,
    )
    return MeteredQuoteResponse(total=str(total), currency=breakdown["currency"], breakdown=breakdown)


# ── Buyer: track order ────────────────────────────────────────────────────────

@router.get("/{order_id}/track", response_model=DeliveryRead)
def track_delivery(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    delivery = (
        db.query(Delivery)
        .join(Order, Delivery.order_id == Order.id)
        .filter(
            Delivery.order_id == order_id,
            Order.order_group.has(buyer_id=current_user.id),
        )
        .first()
    )
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    return delivery


@router.get("/{order_id}/track/live", response_model=DeliveryTrackingRead)
def track_delivery_live(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Enhanced tracking with agent location, route, and ETA for customer."""
    delivery = (
        db.query(Delivery)
        .options(
            selectinload(Delivery.order).selectinload(Order.buyer),
            selectinload(Delivery.order).selectinload(Order.shop),
            selectinload(Delivery.agent),
        )
        .join(Order, Delivery.order_id == Order.id)
        .filter(
            Delivery.order_id == order_id,
            Order.order_group.has(buyer_id=current_user.id),
        )
        .first()
    )
    if not delivery:
        raise HTTPException(404, "Delivery not found")

    # Build agent location info
    agent_info = None
    if delivery.agent:
        agent_info = AgentLocationRead(
            agent_id=delivery.agent.id,
            name=delivery.agent.name,
            lat=delivery.agent.current_lat,
            lng=delivery.agent.current_lng,
            last_update=delivery.agent.last_location_update,
            status=delivery.agent.status,
        )

    # Determine human-readable status
    status_map = {
        DeliveryStatus.pending: "Order placed, waiting for rider",
        DeliveryStatus.assigned: "Rider assigned, heading to pickup",
        DeliveryStatus.picked: "Order picked up, on the way",
        DeliveryStatus.in_transit: "En route to you",
        DeliveryStatus.delivered: "Delivered",
        DeliveryStatus.cancelled: "Cancelled",
    }
    status_display = status_map.get(delivery.status, delivery.status.value)

    # Calculate distance remaining if agent has location and delivery address has coords
    distance_remaining = None
    if delivery.agent and delivery.agent.current_lat and delivery.agent.current_lng:
        address = delivery.order.delivery_address or {}
        buyer_lat = address.get("lat")
        buyer_lng = address.get("lng")
        if buyer_lat and buyer_lng:
            from math import radians, sin, cos, sqrt, atan2
            R = 6371  # Earth radius in km
            lat1, lon1 = radians(delivery.agent.current_lat), radians(delivery.agent.current_lng)
            lat2, lon2 = radians(float(buyer_lat)), radians(float(buyer_lng))
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
            distance_remaining = R * 2 * atan2(sqrt(a), sqrt(1-a))

    # Check if OTP is required (only for in_transit status)
    otp_required = delivery.status == DeliveryStatus.in_transit

    return DeliveryTrackingRead(
        delivery=delivery,
        agent=agent_info,
        route=None,  # TODO: integrate with routing service for full route
        estimated_arrival=delivery.estimated_at,
        distance_remaining_km=round(distance_remaining, 2) if distance_remaining else None,
        status_display=status_display,
        can_contact_agent=delivery.status in (DeliveryStatus.assigned, DeliveryStatus.picked, DeliveryStatus.in_transit),
        otp_required=otp_required,
    )


@router.get("/{delivery_id}", response_model=DeliveryRead)
def get_delivery_detail(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    delivery = (
        db.query(Delivery)
        .options(
            selectinload(Delivery.order).selectinload(Order.buyer),
            selectinload(Delivery.order).selectinload(Order.items),
            selectinload(Delivery.order).selectinload(Order.shop),
        )
        .filter(Delivery.id == delivery_id, Delivery.agent_id == agent.id)
        .first()
    )
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    return delivery


# ── Batch/Multi-order dispatch ──────────────────────────────────────────────────

@router.post(
    "/batches",
    response_model=DeliveryBatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a delivery batch from multiple deliveries (admin/auto)",
)
def create_delivery_batch(
    payload: DeliveryBatchCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Create a batch from multiple deliveries. Validates they share the same pickup area."""
    if len(payload.delivery_ids) < 2:
        raise HTTPException(400, "Batch must contain at least 2 deliveries")

    deliveries = db.query(Delivery).filter(Delivery.id.in_(payload.delivery_ids)).all()
    if len(deliveries) != len(payload.delivery_ids):
        raise HTTPException(404, "One or more deliveries not found")

    # Validate all deliveries are in 'assigned' status and unbatched
    for d in deliveries:
        if d.status != DeliveryStatus.assigned:
            raise HTTPException(400, f"Delivery {d.id} is not in 'assigned' status")
        if d.batch_id is not None:
            raise HTTPException(400, f"Delivery {d.id} is already in a batch")

    # Calculate pickup location (use first delivery's shop location)
    first_order = deliveries[0].order
    shop = first_order.shop
    if not shop or not shop.lat or not shop.lng:
        raise HTTPException(400, "Pickup location (shop) not found for batching")

    # Verify all deliveries are from the same shop/area
    for d in deliveries[1:]:
        if d.order.shop_id != shop.id:
            raise HTTPException(400, "All deliveries in a batch must be from the same shop")

    # Calculate total distance and estimated duration
    total_distance = 0.0
    for d in deliveries:
        if d.distance_km:
            total_distance += d.distance_km

    batch = DeliveryBatch(
        pickup_lat=shop.lat,
        pickup_lng=shop.lng,
        pickup_address=f"{shop.name}, {shop.town or ''}, {shop.county or ''}".strip(", "),
        total_distance_km=total_distance,
        estimated_duration_min=sum(d.duration_min or 0 for d in deliveries),
    )
    db.add(batch)
    db.flush()

    # Assign deliveries to batch
    for d in deliveries:
        d.batch_id = batch.id

    db.commit()
    db.refresh(batch)
    return batch


@router.get(
    "/batches",
    response_model=List[DeliveryBatchRead],
    summary="List delivery batches (admin)",
)
def list_delivery_batches(
    status: Optional[DeliveryBatchStatus] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(DeliveryBatch).options(selectinload(DeliveryBatch.deliveries))
    if status:
        query = query.filter(DeliveryBatch.status == status)
    return query.order_by(DeliveryBatch.created_at.desc()).all()


@router.get(
    "/batches/{batch_id}",
    response_model=DeliveryBatchRead,
    summary="Get batch details",
)
def get_delivery_batch(
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    batch = db.query(DeliveryBatch).options(selectinload(DeliveryBatch.deliveries)).filter(DeliveryBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


@router.post(
    "/batches/{batch_id}/assign",
    response_model=DeliveryBatchRead,
    summary="Assign batch to a rider",
)
def assign_delivery_batch(
    batch_id: uuid.UUID,
    payload: DeliveryBatchAssign,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    batch = db.query(DeliveryBatch).filter(DeliveryBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")
    if batch.status != DeliveryBatchStatus.created:
        raise HTTPException(400, "Batch already assigned or in progress")

    agent = db.get(DeliveryAgent, payload.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status != DeliveryAgentStatus.active:
        raise HTTPException(400, "Agent must be active to accept batch")

    batch.agent_id = agent.id
    batch.status = DeliveryBatchStatus.assigned
    batch.assigned_at = datetime.now(timezone.utc)

    # Update all deliveries in batch
    for d in batch.deliveries:
        d.agent_id = agent.id

    db.commit()
    db.refresh(batch)
    return batch


@router.patch(
    "/batches/{batch_id}/status",
    response_model=DeliveryBatchRead,
    summary="Update batch status (rider/admin)",
)
def update_batch_status(
    batch_id: uuid.UUID,
    payload: DeliveryBatchStatusUpdate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    batch = db.query(DeliveryBatch).filter(DeliveryBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")

    # Authorization: batch agent or admin
    is_admin = agent.role == UserRole.admin if hasattr(agent, 'role') else False
    if batch.agent_id != agent.id and not is_admin:
        raise HTTPException(403, "Not authorized")

    # Validate transitions
    valid = {
        DeliveryBatchStatus.created: [DeliveryBatchStatus.assigned],
        DeliveryBatchStatus.assigned: [DeliveryBatchStatus.picked],
        DeliveryBatchStatus.picked: [DeliveryBatchStatus.in_transit],
        DeliveryBatchStatus.in_transit: [DeliveryBatchStatus.completed],
    }
    if batch.status in valid and payload.status not in valid[batch.status]:
        raise HTTPException(400, f"Invalid transition from {batch.status.value} to {payload.status.value}")

    batch.status = payload.status
    now = datetime.now(timezone.utc)
    if payload.status == DeliveryBatchStatus.picked:
        batch.picked_at = now
    elif payload.status == DeliveryBatchStatus.completed:
        batch.completed_at = now

    # Update all deliveries in batch
    for d in batch.deliveries:
        if payload.status == DeliveryBatchStatus.picked and d.status == DeliveryStatus.assigned:
            d.status = DeliveryStatus.picked
            d.picked_at = now
        elif payload.status == DeliveryBatchStatus.in_transit and d.status == DeliveryStatus.picked:
            d.status = DeliveryStatus.in_transit
            d.in_transit_at = now
        elif payload.status == DeliveryBatchStatus.completed and d.status == DeliveryStatus.in_transit:
            d.status = DeliveryStatus.delivered
            d.delivered_at = now

    db.commit()
    db.refresh(batch)
    return batch


# ── Safety Toolkit (SOS, Trip Share, Emergency Contacts) ────────────────────────

@router.post(
    "/safety/sos",
    response_model=SafetyAlertRead,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger SOS alert (rider)",
)
async def trigger_sos(
    payload: SafetyAlertCreate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    """Trigger an SOS alert. Immediately notifies emergency contacts and ops."""
    alert = SafetyAlert(
        agent_id=agent.id,
        alert_type=SafetyAlertType.sos,
        status=SafetyAlertStatus.active,
        lat=payload.lat,
        lng=payload.lng,
        message=payload.message or "SOS triggered by rider",
        alert_metadata=payload.alert_metadata or {"source": "manual_sos"},
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    contacts = db.query(EmergencyContact).filter(EmergencyContact.agent_id == agent.id).all()
    for contact in contacts:
        create_notification(
            db,
            user_id=contact.id,
            type="safety_alert",
            title=f"SOS Alert from {agent.name}",
            body=f"Rider {agent.name} triggered SOS. Location: {payload.lat}, {payload.lng}. Message: {payload.message}",
            data={"alert_id": str(alert.id), "lat": payload.lat, "lng": payload.lng},
        )

    return alert


@router.post(
    "/safety/check-in",
    response_model=SafetyAlertRead,
    status_code=status.HTTP_201_CREATED,
    summary="Manual safety check-in (rider)",
)
async def safety_check_in(
    payload: SafetyAlertCreate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    """Rider manually checks in to confirm safety."""
    alert = SafetyAlert(
        agent_id=agent.id,
        alert_type=SafetyAlertType.check_in_missed,
        status=SafetyAlertStatus.resolved,
        lat=payload.lat,
        lng=payload.lng,
        message=payload.message or "Safety check-in",
        alert_metadata=payload.alert_metadata or {"source": "manual_checkin"},
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get(
    "/safety/alerts",
    response_model=List[SafetyAlertRead],
    summary="Get my safety alerts (rider)",
)
def list_my_safety_alerts(
    status: Optional[SafetyAlertStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    query = db.query(SafetyAlert).filter(SafetyAlert.agent_id == agent.id)
    if status:
        query = query.filter(SafetyAlert.status == status)
    return query.order_by(SafetyAlert.triggered_at.desc()).limit(limit).all()


@router.get(
    "/safety/alerts/{alert_id}",
    response_model=SafetyAlertRead,
    summary="Get safety alert details",
)
def get_safety_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    alert = db.query(SafetyAlert).filter(
        SafetyAlert.id == alert_id,
        SafetyAlert.agent_id == agent.id,
    ).first()
    if not alert:
        raise HTTPException(404, "Safety alert not found")
    return alert


@router.patch(
    "/safety/alerts/{alert_id}",
    response_model=SafetyAlertRead,
    summary="Acknowledge/resolve safety alert (admin/ops)",
)
def acknowledge_safety_alert(
    alert_id: uuid.UUID,
    payload: SafetyAlertAcknowledge,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin/ops acknowledges or resolves a safety alert."""
    alert = db.query(SafetyAlert).filter(SafetyAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Safety alert not found")

    alert.status = payload.status
    if payload.status in (SafetyAlertStatus.acknowledged, SafetyAlertStatus.resolved):
        alert.acknowledged_at = datetime.now(timezone.utc)
    if payload.status == SafetyAlertStatus.resolved:
        alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert


# Emergency Contacts
@router.post(
    "/emergency-contacts",
    response_model=EmergencyContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add emergency contact",
)
def create_emergency_contact(
    payload: EmergencyContactCreate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    if payload.is_primary:
        db.query(EmergencyContact).filter(
            EmergencyContact.agent_id == agent.id,
            EmergencyContact.is_primary == True,
        ).update({"is_primary": False})

    contact = EmergencyContact(
        agent_id=agent.id,
        name=payload.name,
        phone=payload.phone,
        contact_relationship=payload.contact_relationship,
        is_primary=payload.is_primary,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get(
    "/emergency-contacts",
    response_model=List[EmergencyContactRead],
    summary="List my emergency contacts",
)
def list_emergency_contacts(
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    return db.query(EmergencyContact).filter(EmergencyContact.agent_id == agent.id).order_by(EmergencyContact.is_primary.desc()).all()


@router.patch(
    "/emergency-contacts/{contact_id}",
    response_model=EmergencyContactRead,
    summary="Update emergency contact",
)
def update_emergency_contact(
    contact_id: uuid.UUID,
    payload: EmergencyContactUpdate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    contact = db.query(EmergencyContact).filter(
        EmergencyContact.id == contact_id,
        EmergencyContact.agent_id == agent.id,
    ).first()
    if not contact:
        raise HTTPException(404, "Emergency contact not found")

    if payload.is_primary:
        db.query(EmergencyContact).filter(
            EmergencyContact.agent_id == agent.id,
            EmergencyContact.is_primary == True,
        ).update({"is_primary": False})

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact


@router.delete(
    "/emergency-contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete emergency contact",
)
def delete_emergency_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    contact = db.query(EmergencyContact).filter(
        EmergencyContact.id == contact_id,
        EmergencyContact.agent_id == agent.id,
    ).first()
    if not contact:
        raise HTTPException(404, "Emergency contact not found")
    db.delete(contact)
    db.commit()


# Trip Sharing
@router.post(
    "/trip-share",
    response_model=TripShareRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shareable trip link",
)
def create_trip_share(
    payload: TripShareCreate,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    """Create a shareable link for real-time trip tracking."""
    delivery = db.query(Delivery).filter(
        Delivery.id == payload.delivery_id,
        Delivery.agent_id == agent.id,
    ).first()
    if not delivery:
        raise HTTPException(404, "Delivery not found or not assigned to you")

    import secrets
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)

    trip_share = TripShare(
        delivery_id=payload.delivery_id,
        token=token,
        expires_at=expires_at,
    )
    db.add(trip_share)
    db.commit()
    db.refresh(trip_share)
    return trip_share



# � GPS Fraud Detection ���������������������

@router.get(
    "/fraud/alerts",
    response_model=GPSFraudAlertListResponse,
    summary="List GPS fraud alerts (admin/ops)",
)
def list_gps_fraud_alerts(
    agent_id: Optional[uuid.UUID] = Query(None),
    fraud_type: Optional[GPSFraudType] = Query(None),
    severity: Optional[GPSFraudSeverity] = Query(None),
    is_reviewed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(GPSFraudAlert)
    if agent_id:
        query = query.filter(GPSFraudAlert.agent_id == agent_id)
    if fraud_type:
        query = query.filter(GPSFraudAlert.fraud_type == fraud_type)
    if severity:
        query = query.filter(GPSFraudAlert.severity == severity)
    if is_reviewed is not None:
        query = query.filter(GPSFraudAlert.is_reviewed == is_reviewed)

    total = query.count()
    results = query.order_by(GPSFraudAlert.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return GPSFraudAlertListResponse(total=total, page=page, limit=limit, results=results)


@router.get(
    "/fraud/alerts/{alert_id}",
    response_model=GPSFraudAlertRead,
    summary="Get GPS fraud alert details",
)
def get_gps_fraud_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    alert = db.query(GPSFraudAlert).filter(GPSFraudAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Fraud alert not found")
    return alert


@router.patch(
    "/fraud/alerts/{alert_id}",
    response_model=GPSFraudAlertRead,
    summary="Review/resolve GPS fraud alert (admin/ops)",
)
def review_gps_fraud_alert(
    alert_id: uuid.UUID,
    payload: GPSFraudAlertReview,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    alert = db.query(GPSFraudAlert).filter(GPSFraudAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Fraud alert not found")

    alert.is_reviewed = True
    alert.resolution = payload.resolution
    alert.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert


@router.get(
    "/fraud/stats",
    response_model=dict,
    summary="Get GPS fraud detection statistics",
)
def get_gps_fraud_stats(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, 30)

    alerts = db.query(GPSFraudAlert).filter(
        GPSFraudAlert.created_at >= since,
        GPSFraudAlert.created_at < until,
    ).all()

    stats = {
        "total": len(alerts),
        "by_type": {},
        "by_severity": {},
        "reviewed": 0,
        "pending_review": 0,
    }

    for alert in alerts:
        stats["by_type"][alert.fraud_type.value] = stats["by_type"].get(alert.fraud_type.value, 0) + 1
        stats["by_severity"][alert.severity.value] = stats["by_severity"].get(alert.severity.value, 0) + 1
        if alert.is_reviewed:
            stats["reviewed"] += 1
        else:
            stats["pending_review"] += 1

    return {
        "period": period or "last_30_days",
        **stats,
    }