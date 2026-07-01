import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.catalog import ProductStatus, ProductCondition


class CategoryRead(BaseModel):
    id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    name: str
    slug: str
    icon_url: Optional[str]
    sort_order: int
    is_active: bool
    children: List["CategoryRead"] = []

    model_config = {"from_attributes": True}

CategoryRead.model_rebuild()


class ProductImageCreate(BaseModel):
    url: str
    thumbnail_url: Optional[str] = None
    alt_text: Optional[str] = None
    sort_order: int = 0
    is_primary: bool = False


class ProductImageRead(BaseModel):
    id: uuid.UUID
    url: str
    thumbnail_url: Optional[str]
    alt_text: Optional[str]
    sort_order: int
    is_primary: bool

    model_config = {"from_attributes": True}


class ProductVariantCreate(BaseModel):
    name: str
    value: str
    price_delta: str = "0.00"
    stock_qty: int = 0
    sku: Optional[str] = None


class ProductVariantUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    price_delta: Optional[str] = None
    stock_qty: Optional[int] = None
    sku: Optional[str] = None


class ProductVariantRead(BaseModel):
    id: uuid.UUID
    name: str
    value: str
    price_delta: str
    stock_qty: int
    sku: Optional[str]

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    category_id: Optional[uuid.UUID] = None
    name: str
    slug: str
    description: Optional[str] = None
    price: str
    compare_price: Optional[str] = None
    sku: Optional[str] = None
    stock_qty: int = 0
    condition: ProductCondition = ProductCondition.new
    status: ProductStatus = ProductStatus.draft
    is_fragile: bool = False
    weight_kg: Optional[str] = None
    dimensions: Optional[str] = None
    tags: Optional[List[str]] = None
    variants: Optional[List[ProductVariantCreate]] = None

class ProductRead(BaseModel):
    id: uuid.UUID
    shop_id: uuid.UUID
    category_id: Optional[uuid.UUID]
    name: str
    slug: str
    description: Optional[str]
    price: str
    compare_price: Optional[str]
    sku: Optional[str]
    stock_qty: int
    condition: ProductCondition
    status: ProductStatus
    is_fragile: bool
    tags: Optional[List[str]]
    popularity: int
    images: List[ProductImageRead] = []
    variants: List[ProductVariantRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}

class ProductListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[ProductRead]

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[str] = None
    compare_price: Optional[str] = None
    stock_qty: Optional[int] = None
    status: Optional[ProductStatus] = None
    tags: Optional[List[str]] = None


class ReviewCreate(BaseModel):
    rating: int
    body: Optional[str] = None


class ReviewRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    buyer_id: Optional[uuid.UUID]
    rating: int
    body: Optional[str]
    helpful_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
