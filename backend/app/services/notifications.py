import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.delivery import Notification


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: Optional[str] = None,
    data: Optional[dict] = None,
) -> Notification:
    notification = Notification(user_id=user_id, type=type, title=title, body=body, data=data)
    db.add(notification)
    return notification
