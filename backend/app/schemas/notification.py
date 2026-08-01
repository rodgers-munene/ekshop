import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: Optional[str]
    data: Optional[Any]
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    unread_count: int
    results: List[NotificationRead]
