import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload
from jose import JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.dependencies.database import get_db
from app.models.messaging import Conversation, Message, ActorRole
from app.models.commerce import Order
from app.models.user import User
from app.schemas.messaging import MessageCreate, MessageRead, ConversationRead

router = APIRouter(prefix="/conversations", tags=["conversations"])
bearer_scheme = HTTPBearer()


def _get_user_from_token(credentials: HTTPAuthorizationCredentials, db: Session) -> Optional[User]:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id or payload.get("type") == "agent":
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.id == uuid.UUID(user_id)).first()


@router.get("", response_model=List[ConversationRead])
def list_conversations(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    user = _get_user_from_token(credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conversations = (
        db.query(Conversation)
        .options(selectinload(Conversation.messages).selectinload(Message.sender))
        .join(Order, Order.id == Conversation.order_id)
        .filter(
            (Order.buyer_id == user.id)
            | (Order.shop.has(seller_id=user.id))
        )
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return conversations


@router.get("/{conversation_id}/messages", response_model=List[MessageRead])
def list_messages(
    conversation_id: uuid.UUID,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    user = _get_user_from_token(credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    order = conversation.order
    if not (order.buyer_id == user.id or order.shop.seller_id == user.id):
        raise HTTPException(403, "Not a participant in this conversation")

    messages = (
        db.query(Message)
        .options(selectinload(Message.sender))
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return messages


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    user = _get_user_from_token(credentials, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    order = conversation.order
    if not (order.buyer_id == user.id or order.shop.seller_id == user.id):
        raise HTTPException(403, "Not a participant in this conversation")

    sender_type = ActorRole.customer if order.buyer_id == user.id else ActorRole.seller

    message = Message(
        conversation_id=conversation_id,
        sender_id=user.id,
        sender_type=sender_type,
        body=payload.body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
