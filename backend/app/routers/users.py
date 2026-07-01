from fastapi import APIRouter, HTTPException, Depends, status
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import update, delete

from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.user import User
from app.models.delivery import Notification as NotificationModel
from app.models.commerce import UserAddress, Wishlist
from app.models.analytics import EventType
from app.schemas.user import UserRead, UserUpdate, Notification
from app.schemas.commerce import UserAddressRead, UserAddressCreate, UserAddressUpdate
from app.schemas.catalog import ProductRead
from app.services import recommendations as rec_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get my profile",
    description="Returns the profile of the currently authenticated user.",
)
def get_profile_details(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.patch(
    "/me",
    response_model=UserRead,
)
def update_profile_details(payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Update the current user's profile
    update_stmt = (
        update(User)
        .where(User.id == current_user.id)
        #  turns the Pydantic object into a plain dict, but only includes fields the client actually sent.
        .values(**payload.model_dump(exclude_unset=True))
    )
    db.execute(update_stmt)
    db.commit()
    db.refresh(current_user)
    
    return current_user

# get addresses
@router.get(
    "/me/addresses",
    response_model=list[UserAddressRead],
)
def get_user_addresses(current_user: User = Depends(get_current_active_user)):
    return current_user.addresses

# create a new address
@router.post(
    "/me/addresses",
    response_model=UserAddressRead,
    status_code=status.HTTP_201_CREATED
)
def create_user_address(payload: UserAddressCreate, db: Session = Depends(get_db), currentUser: User = Depends(get_current_active_user)):
    address = UserAddress(**payload.model_dump(), user_id=currentUser.id)
    db.add(address)
    db.commit()
    db.refresh(address)
    
    return address

# update address id

@router.patch(
    "/me/addresses/{address_id}",
    response_model=UserAddressRead,
)
def update_user_address(address_id: uuid.UUID, payload: UserAddressUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user.id,
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    update_stmt = (
        update(UserAddress)
        .where(UserAddress.id == address.id, UserAddress.user_id == current_user.id)
        .values(**payload.model_dump(exclude_unset=True))
    )
    
    db.execute(update_stmt)
    db.commit()
    db.refresh(address)
    
    return address

@router.delete(
    "/me/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user_address(address_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user.id,
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    delete_stmt = delete(UserAddress).where(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user.id,
    )
    
    db.execute(delete_stmt)
    db.commit()
    
    
@router.get("/me/wishlist", response_model=list[ProductRead])
def get_wishlist(current_user: User = Depends(get_current_active_user)):
    return [entry.product for entry in current_user.wishlists]


@router.post("/me/wishlist", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def add_to_wishlist(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    existing = db.query(Wishlist).filter(
        Wishlist.user_id == current_user.id,
        Wishlist.product_id == product_id,
    ).first()
    if existing:
        raise HTTPException(409, "Product already in wishlist")

    entry = Wishlist(user_id=current_user.id, product_id=product_id)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    rec_service.log_event(
        db=db,
        session_id=f"user-{current_user.id}",
        event_type=EventType.wishlist,
        user_id=current_user.id,
        product_id=product_id,
    )

    return entry.product


@router.delete("/me/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_wishlist(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    entry = db.query(Wishlist).filter(
        Wishlist.user_id == current_user.id,
        Wishlist.product_id == product_id,
    ).first()
    if not entry:
        raise HTTPException(404, "Product not in wishlist")

    db.delete(entry)
    db.commit()


@router.get(
    "/me/notifications",
    response_model=list[Notification],
    status_code=status.HTTP_200_OK,
    summary="Get user notifications",
)
def get_notifications(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    return current_user.notifications

@router.patch(
    "/me/notifications/{notification_id}/read",
    response_model=Notification,
)
def mark_notification_read(notification_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notification = db.query(NotificationModel).filter(
        NotificationModel.user_id == current_user.id,
        NotificationModel.id == notification_id,
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    update_stmt = update(NotificationModel).where(
        NotificationModel.user_id == current_user.id,
        NotificationModel.id == notification_id,
    ).values(is_read=True)

    db.execute(update_stmt)
    db.commit()
    db.refresh(notification)

    return notification
    