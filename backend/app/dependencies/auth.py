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

def require_admin(user: User = Depends(get_current_active_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
    