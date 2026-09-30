import uuid
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.crypto import encrypt_message, decrypt_message
from app.dependencies.database import get_db
from app.models.messaging import Conversation, Message, ActorRole, conversation_participants
from app.models.commerce import Order
from app.models.user import User
from app.models.delivery import DeliveryAgent, Delivery
from app.schemas.messaging import MessageRead
from app.services.notifications import create_notification

router = APIRouter(tags=["messaging-ws"])

logger = logging.getLogger(__name__)

active_connections: Dict[str, Set[WebSocket]] = {}


def _authenticate(token: str, db: Session):
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id:
            raise HTTPException(401, "Invalid token")
        if token_type == "agent":
            agent = db.query(DeliveryAgent).filter(DeliveryAgent.id == uuid.UUID(user_id)).first()
            if not agent:
                raise HTTPException(401, "Agent not found")
            return {"type": "agent", "id": agent.id, "name": agent.name}
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if not user:
            raise HTTPException(401, "User not found")
        return {"type": user.role.value, "id": user.id, "name": user.name}
    except JWTError:
        raise HTTPException(401, "Invalid token")


def _is_ws_participant(identity: dict, conversation: Conversation, db: Session) -> bool:
    """Authorization for the websocket: mirrors the REST participant check."""
    agent_id = conversation_participants.c.agent_id == identity["id"] if identity["type"] == "agent" else None
    if agent_id is not None:
        row = db.execute(
            conversation_participants.select().where(
                conversation_participants.c.conversation_id == conversation.id,
                conversation_participants.c.agent_id == identity["id"],
            )
        ).first()
        if row is not None:
            return True

    if conversation.order_id is None:
        return identity["id"] in {p.id for p in conversation.participants}

    order = db.query(Order).filter(Order.id == conversation.order_id).first()
    if not order:
        return False
    if identity["type"] == "agent":
        delivery = (
            db.query(Delivery.id)
            .filter(Delivery.order_id == conversation.order_id, Delivery.agent_id == identity["id"])
            .first()
        )
        return delivery is not None
    return order.buyer_id == identity["id"] or (order.shop and order.shop.seller_id == identity["id"])


@router.websocket("/ws/conversations/{conversation_id}")
async def websocket_conversation(
    websocket: WebSocket,
    conversation_id: str,
    token: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()
    try:
        identity = _authenticate(token, db)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    conv = db.query(Conversation).filter(Conversation.id == uuid.UUID(conversation_id)).first()
    if not conv:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not _is_ws_participant(identity, conv, db):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room_key = str(conv.id)
    if room_key not in active_connections:
        active_connections[room_key] = set()
    active_connections[room_key].add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            body = payload.get("body", "").strip()
            if not body:
                continue

            encrypted = encrypt_message(body)
            # messages.sender_id is a users.id foreign key; agents are not users.
            sender_id = None if identity["type"] == "agent" else identity["id"]
            message = Message(
                conversation_id=conv.id,
                sender_id=sender_id,
                sender_type=(
                    ActorRole.agent
                    if identity["type"] == "agent"
                    else (ActorRole.admin if identity["type"] == "admin" else ActorRole.customer)
                ),
                body=encrypted,
            )
            db.add(message)
            conv.last_message_at = message.created_at
            db.commit()
            db.refresh(message)

            _notify_ws_participants(db, conv, identity, message)

            read_model = MessageRead(
                id=message.id,
                conversation_id=message.conversation_id,
                sender_id=message.sender_id,
                sender_type=message.sender_type,
                body=decrypt_message(message.body),
                created_at=message.created_at,
            )
            await _broadcast(room_key, read_model.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        active_connections[room_key].discard(websocket)
        if not active_connections[room_key]:
            del active_connections[room_key]


async def _broadcast(room_key: str, message: dict) -> None:
    dead: Set[WebSocket] = set()
    for ws in active_connections.get(room_key, set()):
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        active_connections[room_key].discard(ws)


def _notify_ws_participants(
    db: Session,
    conversation: Conversation,
    identity: dict,
    message: Message,
) -> None:
    """Create notifications for all conversation participants except the sender (WebSocket version)."""
    participants = set()

    if conversation.order_id is None:
        for p in conversation.participants:
            participants.add(("user", p.id))
    else:
        order = db.query(Order).filter(Order.id == conversation.order_id).first()
        if order:
            participants.add(("user", order.buyer_id))
            if order.shop:
                participants.add(("user", order.shop.seller_id))

        delivery = db.query(Delivery).filter(Delivery.order_id == conversation.order_id).first()
        if delivery and delivery.agent_id:
            participants.add(("agent", delivery.agent_id))

    if identity["type"] == "agent":
        sender_key = ("agent", identity["id"])
    else:
        sender_key = ("user", identity["id"])

    for p_type, p_id in participants:
        if (p_type, p_id) != sender_key:
            create_notification(
                db,
                user_id=p_id,
                type="new_message",
                title="New message",
                body=f"You have a new message in conversation {conversation.id}",
                data={"conversation_id": str(conversation.id), "message_id": str(message.id)},
            )
