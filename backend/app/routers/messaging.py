import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.messaging import Conversation, Message
from app.models.shop import Shop
from app.models.user import User
from app.schemas.messaging import (
    ConversationCreate,
    ConversationRead,
    ConversationSummary,
    MessageCreate,
    MessageRead,
)
from app.services.notifications import create_notification

router = APIRouter(prefix="/conversations", tags=["messaging"])


def _get_conversation_for_participant(db: Session, conversation_id: uuid.UUID, user: User) -> Conversation:
    conversation = (
        db.query(Conversation)
        .join(Shop, Conversation.shop_id == Shop.id)
        .filter(
            Conversation.id == conversation_id,
            or_(Conversation.buyer_id == user.id, Shop.seller_id == user.id),
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def start_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.id == payload.shop_id).first()
    if not shop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")
    if shop.seller_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't start a conversation with your own shop")

    conversation = (
        db.query(Conversation)
        .filter(Conversation.buyer_id == current_user.id, Conversation.shop_id == shop.id)
        .first()
    )
    if not conversation:
        conversation = Conversation(buyer_id=current_user.id, shop_id=shop.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    return conversation


@router.get("", response_model=List[ConversationSummary])
def list_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    conversations = (
        db.query(Conversation)
        .join(Shop, Conversation.shop_id == Shop.id)
        .filter(or_(Conversation.buyer_id == current_user.id, Shop.seller_id == current_user.id))
        .order_by(Conversation.last_message_at.desc())
        .all()
    )

    summaries = []
    for conversation in conversations:
        last_message = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        unread_count = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id,
                Message.is_read == False,
                Message.sender_id != current_user.id,
            )
            .count()
        )
        summaries.append(
            ConversationSummary(
                id=conversation.id,
                buyer_id=conversation.buyer_id,
                shop_id=conversation.shop_id,
                shop_name=conversation.shop.name if conversation.shop else None,
                buyer_name=f"{conversation.buyer.first_name} {conversation.buyer.last_name}" if conversation.buyer else None,
                last_message_at=conversation.last_message_at,
                last_message_body=last_message.body if last_message else None,
                unread_count=unread_count,
            )
        )
    return summaries


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    conversation = _get_conversation_for_participant(db, conversation_id, current_user)
    conversation.messages.sort(key=lambda m: m.created_at)
    return conversation


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    conversation = _get_conversation_for_participant(db, conversation_id, current_user)

    message = Message(conversation_id=conversation.id, sender_id=current_user.id, body=payload.body)
    db.add(message)
    conversation.last_message_at = datetime.now(timezone.utc)

    recipient_id = conversation.shop.seller_id if current_user.id == conversation.buyer_id else conversation.buyer_id
    create_notification(
        db,
        user_id=recipient_id,
        type="new_message",
        title="New message",
        body=payload.body[:200],
        data={"conversation_id": str(conversation.id)},
    )

    db.commit()
    db.refresh(message)
    return message


@router.patch("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_conversation_read(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    conversation = _get_conversation_for_participant(db, conversation_id, current_user)

    db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.sender_id != current_user.id,
        Message.is_read == False,
    ).update({"is_read": True})
    db.commit()
