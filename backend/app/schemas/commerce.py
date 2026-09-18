import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, field_validator
from app.models.commerce import OrderStatus, OrderGroupStatus
from app.schemas.geography import WardWithLocationRead


class CartItemCreate(BaseModel):
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    quantity: int = 1


class CheckoutCreate(BaseModel):
    address_id: uuid.UUID
    notes: Optional[str] = None


class DeliveryFeePreviewItem(BaseModel):
    product_id: uuid.UUID
    quantity: int = 1


class DeliveryFeePreviewRequest(BaseModel):
    address_id: uuid.UUID
    shop_ids: List[uuid.UUID] = []
    items: List[DeliveryFeePreviewItem] = []


class DeliveryFeeBreakdownItem(BaseModel):
    shop_id: uuid.UUID
    fee: str


class DeliveryFeePreviewResponse(BaseModel):
    total_delivery_fee: str
    breakdown: List[DeliveryFeeBreakdownItem]
    # Everything below is populated only by the cost_based model, which can say
    # why it charged what it charged. Checkout shows this under the fee so the
    # number stops looking arbitrary. The older models leave them unset.
    pricing_model: Optional[str] = None
    band: Optional[str] = None
    band_label: Optional[str] = None
    band_fee: Optional[str] = None
    weight_surcharge: Optional[str] = None
    billable_weight_kg: Optional[str] = None


class UserAddressCreate(BaseModel):
    label: Optional[str] = None
    first_name: str
    last_name: str
    phone: str
    county: str
    town: str
    ward_id: uuid.UUID
    exact_location: str
    apartment: Optional[str] = None
    floor: Optional[str] = None
    is_default: bool = False

    # County is matched against the geography tables by name, so a stray space
    # ("Nairobi ") silently breaks the sub-county lookup for that address.
    @field_validator("county", "town", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class UserAddressRead(BaseModel):
    id: uuid.UUID
    label: Optional[str]
    first_name: str
    last_name: str
    phone: str
    county: str
    town: str
    ward_id: Optional[uuid.UUID]
    ward: Optional[WardWithLocationRead] = None
    exact_location: Optional[str]
    apartment: Optional[str]
    is_default: bool

    model_config = {"from_attributes": True}


class UserAddressUpdate(BaseModel):
    label: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    county: Optional[str] = None
    town: Optional[str] = None
    ward_id: Optional[uuid.UUID] = None
    exact_location: Optional[str] = None
    apartment: Optional[str] = None
    floor: Optional[str] = None
    is_default: Optional[bool] = None

    @field_validator("county", "town", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v



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

    @field_validator("discount_amount", mode="before")
    @classmethod
    def default_discount_amount(cls, v):
        return v if v is not None else "0.00"


class OrderShopRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    logo_url: Optional[str] = None
    is_verified: bool

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
    buyer_name: Optional[str] = None
    delivery_address: Optional[Any] = None
    shop: Optional[OrderShopRead] = None

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


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
