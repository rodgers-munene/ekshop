import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.delivery import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    unread_count = query.filter(Notification.is_read == False).count()
    results = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return NotificationListResponse(unread_count=unread_count, results=results)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not notification:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
