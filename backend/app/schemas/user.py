import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from app.models.user import UserRole, UserStatus


class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    county: Optional[str] = None
    role: UserRole = UserRole.buyer
    shop_name: Optional[str] = None
    plan_code: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def require_shop_details_for_sellers(self):
        if self.role == UserRole.seller:
            if not self.shop_name or not self.shop_name.strip():
                raise ValueError("shop_name is required when registering as a seller")
            if not self.plan_code:
                raise ValueError("plan_code is required when registering as a seller")
        return self


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    county: Optional[str]
    avatar_url: Optional[str]
    role: UserRole
    status: UserStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    user: UserRead
    authorization_url: Optional[str] = None
    reference: Optional[str] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    county: Optional[str] = None
    avatar_url: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)



class Notification(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: Optional[str]
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
    
