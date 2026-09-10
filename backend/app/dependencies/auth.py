import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.dependencies.database import get_db
from app.models.user import User, UserRole, UserStatus

bearer_scheme = HTTPBearer()

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"} 
)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try: 
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            raise _credentials_error
    except JWTError:
        raise _credentials_error
    
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise _credentials_error
    
    return user

def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if user.status != UserStatus.active:
        raise HTTPException(status_code=403, detail="Account not active. Check your email.")
    return user

def require_seller(user: User = Depends(get_current_active_user)) -> User:
    if user.role != UserRole.seller:
        raise HTTPException(status_code=403, detail="Seller account required")
    return user


# --- Unpaid-seller access -------------------------------------------------
#
# A seller who has verified their email but not yet paid stays `pending`, and
# `get_current_active_user` rightly refuses them: that single check is what
# keeps the subscription paywall default-deny across every seller endpoint.
#
# To let such a seller into the locked dashboard shell, the two dependencies
# below tolerate that one state — and they are applied ONLY to the handful of
# endpoints that shell needs (own profile, own shop, own subscription, and
# starting a payment). Every other endpoint keeps depending on
# get_current_active_user and so keeps failing closed. Widen this by adding it
# to another route deliberately, never by loosening the check above.

def get_current_user_allow_unpaid_seller(user: User = Depends(get_current_user)) -> User:
    """Active users, plus a seller still pending their first payment.

    A pending seller only holds a token at all because `/auth/login` issued
    one, and login does that only once their email is verified — so reaching
    here already implies a verified address. Suspended accounts are still
    refused, as are pending buyers.
    """
    if user.status == UserStatus.active:
        return user
    if user.role == UserRole.seller and user.status == UserStatus.pending:
        return user
    raise HTTPException(status_code=403, detail="Account not active. Check your email.")


def require_seller_allow_unpaid(user: User = Depends(get_current_user_allow_unpaid_seller)) -> User:
    if user.role != UserRole.seller:
        raise HTTPException(status_code=403, detail="Seller account required")
    return user

def require_admin(user: User = Depends(get_current_active_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
    