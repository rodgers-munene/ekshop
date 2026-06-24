import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel
from app.models.commerce import OrderStatus, OrderGroupStatus


class UserAddressCreate(BaseModel):
    label: Optional[str] = None
    first_name: str
    last_name: str
    phone: str
    county: str
    town: str
    exact_location: Optional[str] = None
    apartment: Optional[str] = None
    floor: Optional[str] = None
    is_default: bool = False


class UserAddressRead(BaseModel):
    id: uuid.UUID
    label: Optional[str]
    first_name: str
    last_name: str
    phone: str
    county: str
    town: str
    exact_location: Optional[str]
    apartment: Optional[str]
    is_default: bool

    model_config = {"from_attributes": True}


class CartItemRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID]
    quantity: int
    added_at: datetime

    model_config = {"from_attributes": True}


class CartRead(BaseModel):
    id: uuid.UUID
    items: List[CartItemRead] = []
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderItemRead(BaseModel):
    id: uuid.UUID
    product_id: Optional[uuid.UUID]
    variant_id: Optional[uuid.UUID]
    product_snapshot: Any
    quantity: int
    unit_price: str
    discount_amount: str
    line_total: str

    model_config = {"from_attributes": True}


class OrderRead(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    shop_id: uuid.UUID
    buyer_id: uuid.UUID
    status: OrderStatus
    subtotal: str
    delivery_fee: str
    total: str
    notes: Optional[str]
    items: List[OrderItemRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderGroupRead(BaseModel):
    id: uuid.UUID
    buyer_id: uuid.UUID
    status: OrderGroupStatus
    subtotal: str
    delivery_fee: str
    total: str
    delivery_address: Any
    orders: List[OrderRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}
