import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload
from jose import JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_access_token
from app.core.crypto import encrypt_message, decrypt_message
from app.dependencies.database import get_db
from app.models.messaging import Conversation, Message, ActorRole, conversation_participants
from app.models.commerce import Order
from app.models.user import User
from app.models.delivery import DeliveryAgent
from app.schemas.messaging import MessageCreate, MessageRead, ConversationRead, ConversationCreate
from app.schemas.user import UserRead
from app.models.shop import Shop

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


def _is_participant(identity: Union[User, AuthenticatedIdentity], conversation: Conversation, db: Session) -> bool:
    if conversation.order_id is None:
        user_ids = {p.id for p in conversation.participants}
        if identity.id in user_ids:
            return True
        if isinstance(identity, AuthenticatedIdentity):
            participant = db.execute(
                conversation_participants.select().where(
                    conversation_participants.c.conversation_id == conversation.id,
                    conversation_participants.c.agent_id == identity.id,
                )
            ).first()
            return participant is not None
        return False
    order = db.query(Order).filter(Order.id == conversation.order_id).first()
    if not order:
        return False
    if isinstance(identity, User):
        return order.buyer_id == identity.id or (order.shop and order.shop.seller_id == identity.id)
    return False


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
        conversations = (
            base_query.filter(Conversation.order_id.is_(None) & Conversation.participants.any(id=identity.id))
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
    if not identity or not isinstance(identity, User):
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

        db.execute(
            conversation_participants.insert().values(
                conversation_id=conversation.id,
                agent_id=identity.id,
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
                sender_id=identity.id,
                sender_type=ActorRole.agent,
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

    if isinstance(identity, User):
        sender_type = ActorRole(identity.role.value)
    else:
        sender_type = ActorRole.agent

    message = Message(
        conversation_id=conversation_id,
        sender_id=identity.id,
        sender_type=sender_type,
        body=encrypt_message(payload.body),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
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
