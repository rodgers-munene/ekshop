import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, or_
from jose import JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.core.crypto import encrypt_message, decrypt_message
from app.dependencies.database import get_db
from app.models.messaging import Conversation, Message, ActorRole, conversation_participants
from app.models.commerce import Order
from app.models.user import User, UserRole
from app.models.delivery import DeliveryAgent, Delivery
from app.schemas.messaging import MessageCreate, MessageRead, ConversationRead, ConversationCreate
from app.schemas.user import UserRead
from app.models.shop import Shop
from app.services.notifications import create_notification

router = APIRouter(prefix="/conversations", tags=["conversations"])
bearer_scheme = HTTPBearer()


class AuthenticatedIdentity:
    def __init__(self, type: str, id: uuid.UUID, name: str):
        self.type = type
        self.id = id
        self.name = name


def _get_user_from_token(credentials: HTTPAuthorizationCredentials, db: Session) -> Optional[Union[User, AuthenticatedIdentity]]:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    if payload.get("type") == "agent":
        agent = db.query(DeliveryAgent).filter(DeliveryAgent.id == uuid.UUID(user_id)).first()
        if not agent:
            return None
        return AuthenticatedIdentity(type="agent", id=agent.id, name=agent.name)

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    return user


def _is_explicit_agent_participant(conversation_id: uuid.UUID, agent_id: uuid.UUID, db: Session) -> bool:
    participant = db.execute(
        conversation_participants.select().where(
            conversation_participants.c.conversation_id == conversation_id,
            conversation_participants.c.agent_id == agent_id,
        )
    ).first()
    return participant is not None


def _agent_delivers_order(order_id: uuid.UUID, agent_id: uuid.UUID, db: Session) -> bool:
    delivery = (
        db.query(Delivery.id)
        .filter(Delivery.order_id == order_id, Delivery.agent_id == agent_id)
        .first()
    )
    return delivery is not None


def _actor_role(identity: Union[User, AuthenticatedIdentity]) -> ActorRole:
    """Map an authenticated identity onto a message actor role.

    UserRole.buyer has no ActorRole equivalent; buyers post as ActorRole.customer.
    """
    if isinstance(identity, AuthenticatedIdentity):
        return ActorRole.agent
    if identity.role == UserRole.seller:
        return ActorRole.seller
    if identity.role == UserRole.admin:
        return ActorRole.admin
    return ActorRole.customer


def _notify_conversation_participants(
    db: Session,
    conversation: Conversation,
    sender: Union[User, AuthenticatedIdentity],
    message: Message,
) -> None:
    """Create notifications for all conversation participants except the sender."""
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

    if isinstance(sender, User):
        sender_key = ("user", sender.id)
    else:
        sender_key = ("agent", sender.id)

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


def _is_participant(identity: Union[User, AuthenticatedIdentity], conversation: Conversation, db: Session) -> bool:
    if isinstance(identity, AuthenticatedIdentity):
        if _is_explicit_agent_participant(conversation.id, identity.id, db):
            return True
        if conversation.order_id is None:
            return False
        return _agent_delivers_order(conversation.order_id, identity.id, db)

    if conversation.order_id is None:
        return identity.id in {p.id for p in conversation.participants}

    order = db.query(Order).filter(Order.id == conversation.order_id).first()
    if not order:
        return False
    return order.buyer_id == identity.id or (order.shop and order.shop.seller_id == identity.id)


@router.get("", response_model=List[ConversationRead])
def list_conversations(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    identity = _get_user_from_token(credentials, db)
    if not identity:
        raise HTTPException(status_code=401, detail="Not authenticated")

    base_query = (
        db.query(Conversation)
        .options(selectinload(Conversation.messages).selectinload(Message.sender))
    )

    if isinstance(identity, User):
        conversations = (
            base_query.join(Order, Order.id == Conversation.order_id, isouter=True)
            .filter(
                (Conversation.order_id.is_(None) & Conversation.participants.any(id=identity.id))
                | (Order.buyer_id == identity.id)
                | (Order.shop.has(seller_id=identity.id))
            )
            .order_by(Conversation.created_at.desc())
            .all()
        )
    else:
        agent_participant = (
            select(Conversation.id)
            .select_from(conversation_participants)
            .where(
                conversation_participants.c.conversation_id == Conversation.id,
                conversation_participants.c.agent_id == identity.id,
            )
            .exists()
        )
        agent_delivery = (
            select(Delivery.id)
            .where(
                Delivery.order_id == Conversation.order_id,
                Delivery.agent_id == identity.id,
            )
            .exists()
        )
        conversations = (
            base_query.filter(or_(agent_participant, agent_delivery))
            .order_by(Conversation.created_at.desc())
            .all()
        )
    return conversations


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    identity = _get_user_from_token(credentials, db)
    if not identity:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Delivery agents may only open support conversations. The remaining branches
    # write the caller's id into a users.id foreign key, which an agent id is not.
    if isinstance(identity, AuthenticatedIdentity):
        if not payload.admin_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agents can only start conversations with support",
            )
    elif not isinstance(identity, User):
        raise HTTPException(status_code=401, detail="Not authenticated")

    if payload.shop_id:
        shop = db.query(Shop).filter(Shop.id == payload.shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")

        conversation = Conversation(
            buyer_id=identity.id,
            shop_id=shop.id,
        )
        db.add(conversation)
        db.flush()

        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=identity.id,
                joined_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=shop.seller_id,
                joined_at=datetime.now(timezone.utc),
            )
        )

        if payload.initial_message:
            message = Message(
                conversation_id=conversation.id,
                sender_id=identity.id,
                sender_type=ActorRole.customer,
                body=encrypt_message(payload.initial_message),
            )
            db.add(message)
            conversation.last_message_at = message.created_at
    elif payload.buyer_id:
        buyer = db.query(User).filter(User.id == payload.buyer_id).first()
        if not buyer:
            raise HTTPException(status_code=404, detail="Buyer not found")

        shop = db.query(Shop).filter(Shop.seller_id == identity.id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Seller shop not found")

        conversation = Conversation(
            buyer_id=buyer.id,
            shop_id=shop.id,
        )
        db.add(conversation)
        db.flush()

        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=buyer.id,
                joined_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=identity.id,
                joined_at=datetime.now(timezone.utc),
            )
        )

        if payload.initial_message:
            message = Message(
                conversation_id=conversation.id,
                sender_id=identity.id,
                sender_type=ActorRole.seller,
                body=encrypt_message(payload.initial_message),
            )
            db.add(message)
            conversation.last_message_at = message.created_at
    elif payload.agent_id:
        agent = db.query(DeliveryAgent).filter(DeliveryAgent.id == payload.agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Delivery agent not found")

        conversation = Conversation()
        db.add(conversation)
        db.flush()

        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=identity.id,
                joined_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                agent_id=agent.id,
                joined_at=datetime.now(timezone.utc),
            )
        )

        if payload.initial_message:
            message = Message(
                conversation_id=conversation.id,
                sender_id=identity.id,
                sender_type=ActorRole.admin if isinstance(identity, User) and identity.role.value == "admin" else ActorRole.customer,
                body=encrypt_message(payload.initial_message),
            )
            db.add(message)
            conversation.last_message_at = message.created_at
    elif payload.admin_id:
        admin = db.query(User).filter(User.id == payload.admin_id, User.role == "admin").first()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        conversation = Conversation()
        db.add(conversation)
        db.flush()

        caller_is_agent = isinstance(identity, AuthenticatedIdentity)
        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                agent_id=identity.id if caller_is_agent else None,
                user_id=None if caller_is_agent else identity.id,
                joined_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=admin.id,
                joined_at=datetime.now(timezone.utc),
            )
        )

        if payload.initial_message:
            message = Message(
                conversation_id=conversation.id,
                sender_id=None if caller_is_agent else identity.id,
                sender_type=ActorRole.agent if caller_is_agent else ActorRole.customer,
                body=encrypt_message(payload.initial_message),
            )
            db.add(message)
            conversation.last_message_at = message.created_at
    elif payload.user_id:
        recipient = db.query(User).filter(User.id == payload.user_id).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="User not found")

        conversation = Conversation()
        db.add(conversation)
        db.flush()

        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=identity.id,
                joined_at=datetime.now(timezone.utc),
            )
        )
        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                user_id=recipient.id,
                joined_at=datetime.now(timezone.utc),
            )
        )

        if payload.initial_message:
            message = Message(
                conversation_id=conversation.id,
                sender_id=identity.id,
                sender_type=ActorRole.admin if isinstance(identity, User) and identity.role.value == "admin" else ActorRole.customer,
                body=encrypt_message(payload.initial_message),
            )
            db.add(message)
            conversation.last_message_at = message.created_at
    else:
        raise HTTPException(status_code=400, detail="Either shop_id, buyer_id, agent_id, admin_id, or user_id must be provided")

    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}/messages", response_model=List[MessageRead])
def list_messages(
    conversation_id: uuid.UUID,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    identity = _get_user_from_token(credentials, db)
    if not identity:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    if not _is_participant(identity, conversation, db):
        raise HTTPException(403, "Not a participant in this conversation")

    messages = (
        db.query(Message)
        .options(selectinload(Message.sender))
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        MessageRead(
            id=m.id,
            conversation_id=m.conversation_id,
            sender_id=m.sender_id,
            sender_type=m.sender_type,
            body=decrypt_message(m.body),
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    identity = _get_user_from_token(credentials, db)
    if not identity:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    if not _is_participant(identity, conversation, db):
        raise HTTPException(403, "Not a participant in this conversation")

    sender_type = _actor_role(identity)

    # messages.sender_id is a users.id foreign key; agents are not users, so their
    # messages are stored with a null sender_id and identified by sender_type.
    sender_id = identity.id if isinstance(identity, User) else None

    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        sender_type=sender_type,
        body=encrypt_message(payload.body),
    )
    db.add(message)
    conversation.last_message_at = message.created_at
    db.commit()
    db.refresh(message)

    _notify_conversation_participants(db, conversation, identity, message)

    return MessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_type=message.sender_type,
        body=decrypt_message(message.body),
        created_at=message.created_at,
    )


@router.get("/support-admin", response_model=UserRead)
def get_support_admin(db: Session = Depends(get_db)):
    admin = db.query(User).filter(User.role == "admin", User.status == "active").order_by(User.created_at.asc()).first()
    if not admin:
        raise HTTPException(status_code=404, detail="No active admin found")
    return admin


# Declared after "/support-admin" so the literal path wins over the uuid path.
@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(
    conversation_id: uuid.UUID,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    identity = _get_user_from_token(credentials, db)
    if not identity:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conversation = (
        db.query(Conversation)
        .options(selectinload(Conversation.messages).selectinload(Message.sender))
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not _is_participant(identity, conversation, db):
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")

    return conversation


@router.patch("/{conversation_id}/read")
def mark_conversation_read(
    conversation_id: uuid.UUID,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    identity = _get_user_from_token(credentials, db)
    if not identity:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not _is_participant(identity, conversation, db):
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")

    query = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.is_read.is_(False),
    )
    if isinstance(identity, User):
        query = query.filter(Message.sender_id != identity.id)

    unread = query.all()
    for message in unread:
        message.is_read = True
    db.commit()

    return {"ok": True, "marked_read": len(unread)}
