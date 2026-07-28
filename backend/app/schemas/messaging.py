import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class MessageCreate(BaseModel):
    body: str


class MessageRead(BaseModel):
    id: uuid.UUID
    sender_id: Optional[uuid.UUID]
    body: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: uuid.UUID
    buyer_id: uuid.UUID
    shop_id: uuid.UUID
    last_message_at: datetime
    messages: List[MessageRead] = []

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    shop_id: uuid.UUID


class ConversationSummary(BaseModel):
    id: uuid.UUID
    buyer_id: uuid.UUID
    shop_id: uuid.UUID
    shop_name: Optional[str] = None
    buyer_name: Optional[str] = None
    last_message_at: datetime
    last_message_body: Optional[str] = None
    unread_count: int = 0

    model_config = {"from_attributes": True}
