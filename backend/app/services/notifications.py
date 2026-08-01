import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.delivery import Notification
from app.models.user import User
from app.services import email as email_service

logger = logging.getLogger(__name__)


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

    user = db.query(User).filter(User.id == user_id).first()
    if user and user.email:
        try:
            email_service.send_notification_email(user.email, title, body or title)
        except Exception as e:
            logger.warning("Failed to send notification email to %s: %s", user.email, e)

    return notification
