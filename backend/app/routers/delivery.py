import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.dependencies.auth import require_admin, get_current_active_user
from app.dependencies.database import get_db
from app.models.delivery import DeliveryAgent, DeliveryAgentStatus, Delivery, DeliveryEvent, DeliveryStatus, ActorRole
from app.models.commerce import Order, OrderStatus
from app.models.user import User
from app.schemas.delivery import (
    AgentLoginRequest, AgentTokenResponse,
    DeliveryAgentCreate, DeliveryAgentRead,
    DeliveryRead, DeliveryStatusUpdate,
)

router = APIRouter(prefix="/delivery", tags=["delivery"])

bearer_scheme = HTTPBearer()

_agent_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired agent token",
    headers={"WWW-Authenticate": "Bearer"},
)

DELIVERY_TRANSITIONS = {
    "assigned":   ["picked", "cancelled"],
    "picked":     ["in_transit"],
    "in_transit": ["delivered", "cancelled"],
}


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


@router.get("/agents", response_model=List[DeliveryAgentRead])
def list_agents(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(DeliveryAgent).all()


# ── Admin: assign delivery ────────────────────────────────────────────────────

@router.post("/{order_id}/assign", response_model=DeliveryRead, status_code=201)
def assign_delivery(
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

    db.commit()
    db.refresh(delivery)
    return delivery


# ── Agent: update delivery status ─────────────────────────────────────────────

@router.patch("/{delivery_id}/status", response_model=DeliveryRead)
def update_delivery_status(
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
    db.commit()
    db.refresh(delivery)
    return delivery


# ── Agent: my deliveries ──────────────────────────────────────────────────────

@router.get("/me", response_model=List[DeliveryRead])
def my_deliveries(
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
):
    return (
        db.query(Delivery)
        .filter(Delivery.agent_id == agent.id)
        .order_by(Delivery.created_at.desc())
        .all()
    )


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
