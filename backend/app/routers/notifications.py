import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.delivery import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationListResponse
from app.services.fcm import send_push_notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class FCMTokenRequest(BaseModel):
    token: str


class PushNotificationRequest(BaseModel):
    title: str
    body: str
    data: Optional[dict] = None


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


# --- FCM / Push Notification Endpoints ---

@router.post("/fcm-token")
def register_fcm_token(
    payload: FCMTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Register or update the user's FCM device token."""
    current_user.fcm_token = payload.token
    db.commit()
    return {"ok": True}


@router.delete("/fcm-token")
def delete_fcm_token(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Remove the user's FCM token (logout / unregister device)."""
    current_user.fcm_token = None
    db.commit()
    return {"ok": True}


@router.post("/push")
async def send_push_notification_endpoint(
    payload: PushNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Send a push notification to the current user's registered device."""
    if not settings.FCM_ENABLED:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Push notifications not enabled")

    success = await send_push_notification(
        user_id=str(current_user.id),
        title=payload.title,
        body=payload.body,
        data=payload.data,
        db_session=db,
    )

    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Failed to send push notification (no FCM token registered)")

    return {"ok": True}


@router.post("/push/admin")
async def admin_send_push_notification(
    payload: PushNotificationRequest,
    user_ids: list[str],
    db: Session = Depends(get_db),
    _: User = Depends(lambda u=Depends(get_current_active_user): u if u.role == "admin" else (_ for _ in ()).throw(HTTPException(status.HTTP_403_FORBIDDEN, "Admin required"))),
):
    """Admin endpoint: send push notification to multiple users."""
    if not settings.FCM_ENABLED:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Push notifications not enabled")

    from app.services.fcm import send_push_to_multiple

    success_count = await send_push_to_multiple(
        user_ids=user_ids,
        title=payload.title,
        body=payload.body,
        data=payload.data,
        db_session=db,
    )

    return {"ok": True, "sent": success_count, "total": len(user_ids)}