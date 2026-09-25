"""Who can see and post in a conversation, shared by the REST and WebSocket routers.

A conversation is one of:
- a shop chat (buyer_id + shop_id, no order): members are the buyer and the seller;
- an order chat (order_id): members come from the order, i.e. the buyer, the
  seller and the delivery agent currently assigned, so a reassigned agent
  gains or loses access automatically;
- a direct chat (neither): admin to user, admin to agent, agent to admin.

Shop and direct chats list their members in conversation_participants.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from jose import JWTError
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_message, encrypt_message
from app.core.security import decode_access_token
from app.models.commerce import Order
from app.models.delivery import Delivery, DeliveryAgent, DeliveryAgentStatus
from app.models.messaging import ActorRole, Conversation, Message, actor_role_for, conversation_participants as cp
from app.models.shop import Shop
from app.models.user import User, UserRole, UserStatus
from app.schemas.messaging import ConversationRead, ConversationSummary, MessageRead
from app.services.notifications import create_notification


@dataclass
class Actor:
    """The signed-in user or delivery agent."""

    user: Optional[User] = None
    agent: Optional[DeliveryAgent] = None

    @property
    def id(self) -> uuid.UUID:
        return self.user.id if self.user else self.agent.id

    @property
    def role(self) -> ActorRole:
        return actor_role_for(self.user.role.value) if self.user else ActorRole.agent

    @property
    def is_admin(self) -> bool:
        return self.user is not None and self.user.role == UserRole.admin


def resolve_actor(token: str, db: Session) -> Optional[Actor]:
    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    sub, token_type = payload.get("sub"), payload.get("type")
    try:
        subject_id = uuid.UUID(sub)
    except (TypeError, ValueError):
        return None

    if token_type == "agent":
        agent = db.query(DeliveryAgent).filter(DeliveryAgent.id == subject_id).first()
        if not agent or agent.status == DeliveryAgentStatus.inactive:
            return None
        return Actor(agent=agent)
    if token_type == "access":
        user = db.query(User).filter(User.id == subject_id).first()
        if not user or user.status != UserStatus.active:
            return None
        return Actor(user=user)
    return None


def _member_column(actor: Actor):
    return cp.c.user_id if actor.user else cp.c.agent_id


def visible_conversations(db: Session, actor: Actor):
    member_of = select(cp.c.conversation_id).where(_member_column(actor) == actor.id)
    if actor.user:
        orders = (
            select(Order.id)
            .join(Shop, Shop.id == Order.shop_id)
            .where(or_(Order.buyer_id == actor.id, Shop.seller_id == actor.id))
        )
    else:
        orders = select(Delivery.order_id).where(Delivery.agent_id == actor.id)
    return db.query(Conversation).filter(
        or_(Conversation.id.in_(member_of), Conversation.order_id.in_(orders))
    )


def can_access_order(actor: Actor, order: Order) -> bool:
    """The buyer, the seller and the currently assigned delivery agent."""
    if actor.user:
        return order.buyer_id == actor.id or (order.shop is not None and order.shop.seller_id == actor.id)
    return order.delivery is not None and order.delivery.agent_id == actor.id


def is_participant(db: Session, actor: Actor, conversation: Conversation) -> bool:
    if conversation.order_id is not None:
        return conversation.order is not None and can_access_order(actor, conversation.order)
    return (
        db.query(cp.c.id)
        .filter(cp.c.conversation_id == conversation.id, _member_column(actor) == actor.id)
        .first()
        is not None
    )


def get_or_create_conversation(db: Session, **key) -> Conversation:
    """Return the conversation matching `key`, creating it if needed. A
    concurrent create (double click) hits the unique index and is re-read."""
    existing = db.query(Conversation).filter_by(**key).first()
    if existing:
        return existing
    try:
        with db.begin_nested():
            conversation = Conversation(**key)
            db.add(conversation)
        return conversation
    except IntegrityError:
        return db.query(Conversation).filter_by(**key).one()


def find_direct_conversation(db: Session, a: Actor, b: Actor) -> Optional[Conversation]:
    query = db.query(Conversation).filter(
        Conversation.order_id.is_(None), Conversation.shop_id.is_(None), Conversation.buyer_id.is_(None)
    )
    for actor in (a, b):
        query = query.filter(
            Conversation.id.in_(select(cp.c.conversation_id).where(_member_column(actor) == actor.id))
        )
    return query.first()


def add_participants(db: Session, conversation: Conversation, actors: Iterable[Actor]) -> None:
    now = datetime.now(timezone.utc)
    for actor in actors:
        values = {"conversation_id": conversation.id, "joined_at": now}
        values["user_id" if actor.user else "agent_id"] = actor.id
        db.execute(pg_insert(cp).values(**values).on_conflict_do_nothing())


def _recipient_user_ids(db: Session, conversation: Conversation, sender: Actor) -> List[uuid.UUID]:
    if conversation.order_id is not None:
        order = conversation.order
        ids = [order.buyer_id, order.shop.seller_id if order.shop else None]
    else:
        ids = [row.user_id for row in db.query(cp.c.user_id).filter(cp.c.conversation_id == conversation.id)]
    return [i for i in dict.fromkeys(ids) if i is not None and not (sender.user and i == sender.id)]


def _sender_role(conversation: Conversation, sender: Actor) -> ActorRole:
    # In shop and order chats the label follows the side of the chat, not the
    # account role: a seller buying from another shop is the customer there,
    # and an admin who owns the shop is its seller.
    if sender.user and conversation.shop is not None:
        if conversation.buyer_id == sender.id:
            return ActorRole.customer
        if conversation.shop.seller_id == sender.id:
            return ActorRole.seller
    return sender.role


def add_message(db: Session, conversation: Conversation, sender: Actor, body: str) -> Message:
    message = Message(
        conversation_id=conversation.id,
        sender_id=sender.id if sender.user else None,
        sender_agent_id=sender.id if sender.agent else None,
        sender_type=_sender_role(conversation, sender),
        body=encrypt_message(body),
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    conversation.last_message_at = message.created_at

    for user_id in _recipient_user_ids(db, conversation, sender):
        create_notification(
            db,
            user_id=user_id,
            type="new_message",
            title="New message",
            body=body[:200],
            data={"conversation_id": str(conversation.id)},
        )
    return message


def _sent_by(message: Message, actor: Actor) -> bool:
    return (message.sender_id if actor.user else message.sender_agent_id) == actor.id


def not_sent_by(actor: Actor):
    column = Message.sender_id if actor.user else Message.sender_agent_id
    return column.is_distinct_from(actor.id)


def _user_name(user: Optional[User]) -> Optional[str]:
    if not user:
        return None
    return " ".join(p for p in (user.first_name, user.last_name) if p) or None


def message_read(message: Message, actor: Actor) -> MessageRead:
    if message.sender_agent is not None:
        sender_name = message.sender_agent.name
    else:
        sender_name = _user_name(message.sender)
    return MessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_agent_id=message.sender_agent_id,
        sender_type=message.sender_type,
        sender_name=sender_name,
        body=decrypt_message(message.body),
        is_read=message.is_read,
        is_mine=_sent_by(message, actor),
        created_at=message.created_at,
    )


def _title(db: Session, conversation: Conversation, actor: Actor) -> str:
    if conversation.order_id is not None:
        return f"Order #{str(conversation.order_id)[:8].upper()}"
    if conversation.shop_id is not None:
        if actor.user and actor.id == conversation.buyer_id:
            return conversation.shop.name if conversation.shop else "Shop"
        return _user_name(conversation.buyer) or "Customer"

    rows = db.query(cp.c.user_id, cp.c.agent_id).filter(cp.c.conversation_id == conversation.id).all()
    names = []
    for user_id, agent_id in rows:
        if actor.user and user_id == actor.id or actor.agent and agent_id == actor.id:
            continue
        if user_id:
            user = db.get(User, user_id)
            names.append("Ekshop support" if actor.agent and user and user.role == UserRole.admin else _user_name(user))
        else:
            agent = db.get(DeliveryAgent, agent_id)
            names.append(agent.name if agent else None)
    return ", ".join(n for n in names if n) or "Conversation"


def _summary_fields(db: Session, conversation: Conversation, actor: Actor) -> dict:
    return {
        "id": conversation.id,
        "buyer_id": conversation.buyer_id,
        "shop_id": conversation.shop_id,
        "order_id": conversation.order_id,
        "title": _title(db, conversation, actor),
        "shop_name": conversation.shop.name if conversation.shop else None,
        "buyer_name": _user_name(conversation.buyer),
        "last_message_at": conversation.last_message_at,
        "created_at": conversation.created_at,
    }


def conversation_summary(db: Session, conversation: Conversation, actor: Actor) -> ConversationSummary:
    last_message = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .first()
    )
    unread_count = (
        db.query(func.count(Message.id))
        .filter(Message.conversation_id == conversation.id, Message.is_read.is_(False), not_sent_by(actor))
        .scalar()
    )
    return ConversationSummary(
        **_summary_fields(db, conversation, actor),
        last_message_body=decrypt_message(last_message.body) if last_message else None,
        unread_count=unread_count,
    )


def conversation_read(db: Session, conversation: Conversation, actor: Actor) -> ConversationRead:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return ConversationRead(
        **_summary_fields(db, conversation, actor),
        messages=[message_read(m, actor) for m in messages],
    )
