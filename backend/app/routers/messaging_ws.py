import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.crypto import encrypt_message, decrypt_message
from app.dependencies.database import get_db
from app.models.messaging import Conversation, Message, ActorRole
from app.models.commerce import Order
from app.models.user import User
from app.models.delivery import DeliveryAgent
from app.schemas.messaging import MessageCreate, MessageRead

router = APIRouter(tags=["messaging-ws"])

bearer_scheme = HTTPBearer()

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
            message = Message(
                conversation_id=conv.id,
                sender_id=identity["id"],
                sender_type=ActorRole(identity["type"]),
                body=encrypted,
            )
            db.add(message)
            db.commit()
            db.refresh(message)

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
