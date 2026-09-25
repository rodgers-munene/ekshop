import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.messaging import ActorRole


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None
    sender_agent_id: Optional[uuid.UUID] = None
    sender_type: ActorRole
    sender_name: Optional[str] = None
    body: str
    is_read: bool = False
    # Relative to whoever requested it, so clients don't have to compare ids.
    is_mine: bool = False
    created_at: datetime


class ConversationSummary(BaseModel):
    id: uuid.UUID
    buyer_id: Optional[uuid.UUID] = None
    shop_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    # Who the conversation is with, from the requester's side.
    title: str
    shop_name: Optional[str] = None
    buyer_name: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    last_message_body: Optional[str] = None
    unread_count: int = 0


class ConversationRead(ConversationSummary):
    messages: List[MessageRead] = []


class ConversationCreate(BaseModel):
    """Exactly one target: shop_id (buyer to shop), buyer_id (seller to buyer),
    order_id (order chat), agent_id / user_id (admin), admin_id (agent to admin)."""

    shop_id: Optional[uuid.UUID] = None
    buyer_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    admin_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    initial_message: Optional[str] = Field(default=None, max_length=4000)


class SupportAdminRead(BaseModel):
    id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
