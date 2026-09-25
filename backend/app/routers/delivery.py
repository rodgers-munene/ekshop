import uuid
import secrets
import math
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.dependencies.auth import require_admin, get_current_active_user
from app.dependencies.database import get_db
from decimal import Decimal

from app.models.delivery import DeliveryAgent, DeliveryAgentStatus, Delivery, DeliveryEvent, DeliveryIssue, DeliveryStatus, ActorRole
from app.models.commerce import Order, OrderStatus
from app.models.shop import Shop, ShopStatus
from app.models.user import User
from app.schemas.delivery import (
    AgentLoginRequest, AgentTokenResponse,
    AgentStatusUpdate, AgentLocationUpdate,
    DeliveryAgentCreate, DeliveryAgentRead, DeliveryAgentListResponse,
    DeliveryIssueCreate, DeliveryIssueRead,
    DeliveryRead, DeliveryStatusUpdate,
    DeliveryRateRead, DeliveryRateUpdate,
    DeliverySimulationRow, DeliverySimulationResponse,
    RouteOptimizationRequest, RouteOptimizationResponse, RouteOptimizationStop,
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

router = APIRouter(prefix="/delivery", tags=["delivery"])

bearer_scheme = HTTPBearer()

_agent_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired agent token",
    headers={"WWW-Authenticate": "Bearer"},
)

# How old a rider's last GPS fix can be and still be used for the delivered check.
LOCATION_FRESHNESS = timedelta(minutes=10)

# Earnings shown to riders until per-delivery pay is stored with each delivery.
RIDER_PAY_PER_DELIVERY = 150

DELIVERY_TRANSITIONS = {
    "assigned":   ["picked", "cancelled"],
    "picked":     ["in_transit"],
    "in_transit": ["delivered", "cancelled"],
}


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

    delivery.agent_id = agent_id
    delivery.status = DeliveryStatus.assigned
    if not delivery.estimated_at:
        sla_hours = get_or_create_rate_settings(db).standard_delivery_hours
        delivery.estimated_at = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

    if delivery.distance_km is None and order.shop and order.delivery_address:
        shop = order.shop
        # delivery_address is the JSON snapshot taken at checkout, not an Address row.
        buyer_lat = order.delivery_address.get("lat")
        buyer_lng = order.delivery_address.get("lng")
        if shop.lat and shop.lng and buyer_lat and buyer_lng:
            route = await get_route_eta_distance(shop.lat, shop.lng, float(buyer_lat), float(buyer_lng))
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

    now = datetime.now(timezone.utc)
    delivery.status = payload.status

    if payload.status == DeliveryStatus.picked:
        delivery.picked_at = now
    elif payload.status == DeliveryStatus.in_transit:
        delivery.in_transit_at = now
    elif payload.status == DeliveryStatus.delivered:
        address = delivery.order.delivery_address or {}
        buyer_lat = address.get("lat")
        buyer_lng = address.get("lng")
        # Only a recent fix counts: a position from hours ago would wrongly block the rider.
        location_is_fresh = (
            agent.last_location_update is not None
            and now - agent.last_location_update <= LOCATION_FRESHNESS
        )
        if buyer_lat and buyer_lng and agent.current_lat is not None and agent.current_lng is not None and location_is_fresh:
            distance = _haversine(agent.current_lat, agent.current_lng, float(buyer_lat), float(buyer_lng))
            if distance > 0.5:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"You must be within 500m of the delivery address to mark as delivered. Current distance: {distance:.2f} km",
                )
        delivery.delivered_at = now
        agent.total_deliveries += 1
        agent.status = DeliveryAgentStatus.active
        agent.current_order_id = None

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
    """Riders go online (active) or offline (inactive). Busy is set by assignment."""
    if payload.status == DeliveryAgentStatus.busy:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Busy is set automatically when a delivery is assigned")
    has_open_delivery = (
        db.query(Delivery.id)
        .filter(
            Delivery.agent_id == agent.id,
            Delivery.status.in_([DeliveryStatus.assigned, DeliveryStatus.picked, DeliveryStatus.in_transit]),
        )
        .first()
        is not None
    )
    if payload.status == DeliveryAgentStatus.inactive and has_open_delivery:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Finish or hand back your open deliveries before going offline")
    agent.status = DeliveryAgentStatus.busy if has_open_delivery else payload.status
    db.commit()
    db.refresh(agent)
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

    weekly_earnings = weekly * RIDER_PAY_PER_DELIVERY
    monthly_earnings = monthly * RIDER_PAY_PER_DELIVERY

    return {
        "total_deliveries": agent.total_deliveries,
        "weekly_deliveries": weekly,
        "monthly_deliveries": monthly,
        "weekly_earnings": str(weekly_earnings),
        "monthly_earnings": str(monthly_earnings),
    }


@router.post("/optimize-route", response_model=RouteOptimizationResponse)
async def optimize_route(
    payload: RouteOptimizationRequest,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    """Suggest a stop order: nearest next stop, starting from the rider's
    position when known. Stops without coordinates go last, unordered."""
    deliveries = (
        db.query(Delivery)
        .options(selectinload(Delivery.order).selectinload(Order.buyer))
        .filter(Delivery.id.in_(payload.delivery_ids), Delivery.agent_id == agent.id)
        .all()
    )
    if not deliveries:
        raise HTTPException(404, "No deliveries found")

    located: List[RouteOptimizationStop] = []
    unlocated: List[RouteOptimizationStop] = []
    for d in deliveries:
        addr = d.order.delivery_address or {}
        lat, lng = addr.get("lat"), addr.get("lng")
        buyer = d.order.buyer
        stop = RouteOptimizationStop(
            delivery_id=d.id,
            tracking_number=d.tracking_number or "",
            buyer_name=f"{buyer.first_name} {buyer.last_name}".strip() if buyer else "Customer",
            address=", ".join(p.strip() for p in (addr.get("exact_location") or addr.get("town"), addr.get("county")) if p and p.strip()),
            lat=float(lat) if lat else None,
            lng=float(lng) if lng else None,
        )
        (located if stop.lat is not None and stop.lng is not None else unlocated).append(stop)

    if not located:
        return RouteOptimizationResponse(stops=unlocated)

    # Point 0 is where the rider starts: their current position, or the first stop.
    has_origin = agent.current_lat is not None and agent.current_lng is not None
    coords = [(s.lat, s.lng) for s in located]
    if has_origin:
        coords.insert(0, (agent.current_lat, agent.current_lng))

    matrix = await get_route_matrix(coords)
    if matrix is None:
        matrix = [
            [{"distance_km": _haversine(*a, *b), "duration_min": None} for b in coords]
            for a in coords
        ]

    def leg_km(i: int, j: int) -> float:
        km = matrix[i][j]["distance_km"]
        return km if km is not None else _haversine(*coords[i], *coords[j])

    offset = 1 if has_origin else 0
    path = [0]
    unvisited = set(range(1, len(coords)))
    total_dist = 0.0
    total_dur = 0.0
    has_durations = True
    while unvisited:
        last = path[-1]
        nxt = min(unvisited, key=lambda j: leg_km(last, j))
        dist = leg_km(last, nxt)
        dur = matrix[last][nxt]["duration_min"]
        stop = located[nxt - offset]
        stop.distance_from_previous_km = round(dist, 2)
        stop.duration_from_previous_min = round(dur, 1) if dur is not None else None
        total_dist += dist
        if dur is None:
            has_durations = False
        else:
            total_dur += dur
        path.append(nxt)
        unvisited.discard(nxt)

    ordered = [located[i - offset] for i in path if i - offset >= 0]
    return RouteOptimizationResponse(
        origin_lat=coords[0][0],
        origin_lng=coords[0][1],
        total_distance_km=round(total_dist, 2),
        total_duration_min=round(total_dur, 1) if has_durations else None,
        stops=ordered + unlocated,
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


# ── Buyer: track order ────────────────────────────────────────────────────────

# ── Agent: one delivery ─────────────────────────────────────────────────────────
# Declared after /rates and /simulate so those paths aren't read as a delivery id.

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
