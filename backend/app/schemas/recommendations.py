import uuid
from typing import Optional
from pydantic import BaseModel
from app.models.analytics import EventType


class UserEventCreate(BaseModel):
    session_id: str
    event_type: EventType
    product_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    query: Optional[str] = None
    meta: Optional[dict] = None
