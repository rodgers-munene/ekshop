import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.core.validators import clean_person_name, clean_shop_name, normalize_phone
from app.models.user import UserRole, UserStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str
    last_name: str
    # Required in practice: the county is validated against the counties table
    # in the register endpoint, which has the database session this doesn't.
    phone: str
    county: str
    role: UserRole = UserRole.buyer
    shop_name: Optional[str] = None
    plan_code: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        return clean_person_name(v, "First name")

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str) -> str:
        return clean_person_name(v, "Last name")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @model_validator(mode="after")
    def require_shop_details_for_sellers(self):
        if self.role == UserRole.seller:
            if not self.shop_name or not self.shop_name.strip():
                raise ValueError("shop_name is required when registering as a seller")
            if not self.plan_code:
                raise ValueError("plan_code is required when registering as a seller")
            self.shop_name = clean_shop_name(self.shop_name)
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
    # No payment fields: sellers now open their Paystack transaction by
    # verifying their email, so /auth/verify-email is what returns them.
    user: UserRead


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    county: Optional[str] = None
    avatar_url: Optional[str] = None

    # Same rules as registration, so a profile edit can't reintroduce the data
    # the signup form now rejects.
    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: Optional[str]) -> Optional[str]:
        return clean_person_name(v, "First name") if v is not None else v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: Optional[str]) -> Optional[str]:
        return clean_person_name(v, "Last name") if v is not None else v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return normalize_phone(v) if v is not None else v


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
    
