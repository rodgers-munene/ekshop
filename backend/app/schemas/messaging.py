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
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: uuid.UUID
    order_id: Optional[uuid.UUID] = None
    created_at: datetime
    messages: List[MessageRead] = []

    model_config = {"from_attributes": True}
