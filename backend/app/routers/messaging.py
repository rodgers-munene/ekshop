import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies.database import get_db
from app.models.commerce import Order
from app.models.delivery import DeliveryAgent
from app.models.messaging import Conversation, Message
from app.models.shop import Shop
from app.models.user import User, UserRole, UserStatus
from app.schemas.messaging import (
    ConversationCreate,
    ConversationRead,
    ConversationSummary,
    MessageCreate,
    MessageRead,
    SupportAdminRead,
)
from app.services.messaging import (
    Actor,
    add_message,
    add_participants,
    can_access_order,
    conversation_read,
    conversation_summary,
    find_direct_conversation,
    get_or_create_conversation,
    is_participant,
    message_read,
    not_sent_by,
    resolve_actor,
    visible_conversations,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])
bearer_scheme = HTTPBearer()


def get_actor(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Actor:
    """Buyers, sellers and admins (user tokens) and delivery agents (agent tokens)."""
    actor = resolve_actor(credentials.credentials, db)
    if not actor:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return actor


def _conversation_for(db: Session, conversation_id: uuid.UUID, actor: Actor) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    # 404 for both, so ids of other people's conversations aren't confirmed.
    if not conversation or not is_participant(db, actor, conversation):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.get("", response_model=List[ConversationSummary])
def list_conversations(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    conversations = (
        visible_conversations(db, actor)
        .order_by(func.coalesce(Conversation.last_message_at, Conversation.created_at).desc())
        .all()
    )
    return [conversation_summary(db, c, actor) for c in conversations]


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def start_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    """Open (or resume) a conversation. Starting one that already exists
    returns it, so "Message seller" twice lands in the same thread."""
    targets = [f for f in ("shop_id", "buyer_id", "order_id", "agent_id", "admin_id", "user_id") if getattr(payload, f)]
    if len(targets) != 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide exactly one of shop_id, buyer_id, order_id, agent_id, admin_id or user_id",
        )
    target = targets[0]

    if target == "shop_id":
        if not actor.user:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only customers can message a shop")
        shop = db.get(Shop, payload.shop_id)
        if not shop:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Shop not found")
        if shop.seller_id == actor.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't start a conversation with your own shop")
        conversation = get_or_create_conversation(db, buyer_id=actor.id, shop_id=shop.id, order_id=None)
        add_participants(db, conversation, [actor, Actor(user=shop.seller)])

    elif target == "buyer_id":
        shop = db.query(Shop).filter(Shop.seller_id == actor.id).first() if actor.user else None
        if not shop:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only sellers can message a customer")
        buyer = db.get(User, payload.buyer_id)
        # Sellers can only reach customers who ordered from them, not any account.
        has_ordered = buyer and db.query(Order.id).filter(Order.buyer_id == buyer.id, Order.shop_id == shop.id).first()
        if not has_ordered:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
        conversation = get_or_create_conversation(db, buyer_id=buyer.id, shop_id=shop.id, order_id=None)
        add_participants(db, conversation, [Actor(user=buyer), actor])

    elif target == "order_id":
        order = db.get(Order, payload.order_id)
        if not order or not can_access_order(actor, order):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        conversation = get_or_create_conversation(
            db, order_id=order.id, buyer_id=order.buyer_id, shop_id=order.shop_id
        )

    elif target == "agent_id":
        if not actor.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can message delivery agents")
        agent = db.get(DeliveryAgent, payload.agent_id)
        if not agent:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Delivery agent not found")
        other = Actor(agent=agent)
        conversation = find_direct_conversation(db, actor, other) or Conversation()
        db.add(conversation)
        db.flush()
        add_participants(db, conversation, [actor, other])

    elif target == "admin_id":
        if not actor.agent:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only delivery agents can message support this way")
        admin = db.get(User, payload.admin_id)
        if not admin or admin.role != UserRole.admin or admin.status != UserStatus.active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Admin not found")
        other = Actor(user=admin)
        conversation = find_direct_conversation(db, actor, other) or Conversation()
        db.add(conversation)
        db.flush()
        add_participants(db, conversation, [actor, other])

    else:  # user_id
        if not actor.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can message any user")
        recipient = db.get(User, payload.user_id)
        if not recipient:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        if recipient.id == actor.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't message yourself")
        other = Actor(user=recipient)
        conversation = find_direct_conversation(db, actor, other) or Conversation()
        db.add(conversation)
        db.flush()
        add_participants(db, conversation, [actor, other])

    if payload.initial_message and payload.initial_message.strip():
        add_message(db, conversation, actor, payload.initial_message.strip())

    db.commit()
    db.refresh(conversation)
    return conversation_read(db, conversation, actor)


@router.get("/support-admin", response_model=SupportAdminRead)
def get_support_admin(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """The admin that delivery agents' "Message support" button writes to."""
    admin = (
        db.query(User)
        .filter(User.role == UserRole.admin, User.status == UserStatus.active)
        .order_by(User.created_at.asc())
        .first()
    )
    if not admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active admin found")
    return admin


@router.post("/support", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def open_support_conversation(db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    """Open (or resume) a chat with Ekshop's support desk.

    The desk is a normal shop set by SUPPORT_SHOP_SLUG, so it works like any
    buyer to shop chat. Riders use /support-admin instead.
    """
    if not actor.user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Riders reach support through /conversations/support-admin")
    support_shop = (
        db.query(Shop).filter(Shop.slug == settings.SUPPORT_SHOP_SLUG).first()
        if settings.SUPPORT_SHOP_SLUG
        else None
    )
    if not support_shop:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Support chat is not available right now. Email supportteam@ekshop.store instead.",
        )
    if support_shop.seller_id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't support-chat with your own shop")

    conversation = get_or_create_conversation(db, buyer_id=actor.id, shop_id=support_shop.id, order_id=None)
    add_participants(db, conversation, [actor, Actor(user=support_shop.seller)])
    db.commit()
    db.refresh(conversation)
    return conversation_read(db, conversation, actor)


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    return conversation_read(db, _conversation_for(db, conversation_id, actor), actor)


@router.get("/{conversation_id}/messages", response_model=List[MessageRead])
def list_messages(conversation_id: uuid.UUID, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    return conversation_read(db, _conversation_for(db, conversation_id, actor), actor).messages


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
):
    body = payload.body.strip()
    if not body:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Message can't be empty")
    conversation = _conversation_for(db, conversation_id, actor)
    message = add_message(db, conversation, actor, body)
    db.commit()
    db.refresh(message)
    return message_read(message, actor)


@router.patch("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_conversation_read(conversation_id: uuid.UUID, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)):
    conversation = _conversation_for(db, conversation_id, actor)
    db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.is_read.is_(False),
        not_sent_by(actor),
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
