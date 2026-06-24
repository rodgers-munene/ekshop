import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from app.models.shop import ShopStatus


class ShopCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    county: Optional[str] = None
    town: Optional[str] = None
    exact_location: Optional[str] = None
    phone: Optional[str] = None


class ShopRead(BaseModel):
    id: uuid.UUID
    seller_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    banner_url: Optional[str]
    county: Optional[str]
    town: Optional[str]
    rating_avg: Optional[str]
    rating_count: int
    total_sales: int
    is_verified: bool
    status: ShopStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ShopUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    county: Optional[str] = None
    town: Optional[str] = None
    exact_location: Optional[str] = None
    phone: Optional[str] = None


class ShopPaymentMethodCreate(BaseModel):
    method: str
    details: Optional[dict] = None
    is_primary: bool = False


class ShopPaymentMethodRead(BaseModel):
    id: uuid.UUID
    method: str
    details: Optional[Any]
    is_primary: bool

    model_config = {"from_attributes": True}
