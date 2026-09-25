import json
import uuid
from typing import Dict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.models.messaging import Conversation, Message
from app.services.messaging import Actor, add_message, is_participant, message_read, resolve_actor

router = APIRouter(tags=["messaging-ws"])

# room (conversation id) -> connected sockets and who is on each
active_connections: Dict[str, Dict[WebSocket, Actor]] = {}


@router.websocket("/ws/conversations/{conversation_id}")
async def websocket_conversation(
    websocket: WebSocket,
    conversation_id: str,
    token: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()
    actor = resolve_actor(token, db)
    try:
        conversation = db.get(Conversation, uuid.UUID(conversation_id))
    except ValueError:
        conversation = None
    if not actor or not conversation or not is_participant(db, actor, conversation):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room_key = str(conversation.id)
    active_connections.setdefault(room_key, {})[websocket] = actor

    try:
        while True:
            try:
                payload = json.loads(await websocket.receive_text())
            except ValueError:
                continue
            body = str(payload.get("body", "")).strip() if isinstance(payload, dict) else ""
            if not body or len(body) > 4000:
                continue

            # Access can change mid-connection (e.g. an agent is taken off the order).
            db.refresh(conversation)
            if not is_participant(db, actor, conversation):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break

            message = add_message(db, conversation, actor, body)
            db.commit()
            db.refresh(message)
            await _broadcast(room_key, message)
    except WebSocketDisconnect:
        pass
    finally:
        room = active_connections.get(room_key, {})
        room.pop(websocket, None)
        if not room:
            active_connections.pop(room_key, None)


async def _broadcast(room_key: str, message: Message) -> None:
    room = active_connections.get(room_key, {})
    dead = []
    for ws, viewer in list(room.items()):
        try:
            await ws.send_json(message_read(message, viewer).model_dump(mode="json"))
        except Exception:
            dead.append(ws)
    for ws in dead:
        room.pop(ws, None)
