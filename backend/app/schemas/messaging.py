import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.messaging import ActorRole


class MessageCreate(BaseModel):
    body: str
    sender_type: ActorRole = ActorRole.customer


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: Optional[uuid.UUID]
    sender_type: ActorRole
    body: str
    is_read: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: uuid.UUID
    buyer_id: Optional[uuid.UUID] = None
    shop_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    messages: List[MessageRead] = []

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    shop_id: Optional[uuid.UUID] = None
    buyer_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    admin_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    initial_message: Optional[str] = None
