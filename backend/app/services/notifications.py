import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.commerce import Order
from app.models.delivery import Notification
from app.models.order_notifications import OrderNotificationRecipient
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


def notify_admins_of_new_order(db: Session, order: Order) -> None:
    """Best-effort: email every active order-notification recipient a full
    breakdown of a newly confirmed order, for delivery planning."""
    emails = [
        r.email
        for r in db.query(OrderNotificationRecipient)
        .filter(OrderNotificationRecipient.is_active.is_(True))
        .all()
    ]
    if not emails:
        return
    try:
        email_service.send_new_order_email(emails, order)
    except Exception as e:
        logger.warning("Failed to send new-order admin email for order %s: %s", order.id, e)
