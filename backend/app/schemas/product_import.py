import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.product_import import DuplicateAction, ImportRowStatus, ImportStatus


class ImportRowRead(BaseModel):
    id: uuid.UUID
    row_number: int
    sku: Optional[str] = None
    name: Optional[str] = None
    price: Optional[str] = None
    stock_qty: Optional[int] = None
    brand: Optional[str] = None
    status: ImportRowStatus
    error: Optional[str] = None
    matched_product_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class ImportRowListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[ImportRowRead]


class ImportRead(BaseModel):
    id: uuid.UUID
    shop_id: uuid.UUID
    filename: str
    status: ImportStatus
    category_id: Optional[uuid.UUID] = None
    on_duplicate: DuplicateAction

    total_rows: int
    valid_rows: int
    invalid_rows: int
    # of the valid rows, how many already exist in this shop under the same code
    matched_rows: int

    created_count: int
    updated_count: int
    skipped_count: int
    failed_count: int

    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ImportListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[ImportRead]


class ImportPreview(ImportRead):
    """What the review screen renders: the counts, plus enough rows to show."""

    sample: List[ImportRowRead] = []
    problems: List[ImportRowRead] = []


class ImportCommitRequest(BaseModel):
    category_id: Optional[uuid.UUID] = None
    on_duplicate: DuplicateAction = DuplicateAction.update_stock_price
    limit: int = Field(500, ge=1, le=1000)


class ImportCommitResult(BaseModel):
    status: ImportStatus
    processed: int
    remaining: int
    created_count: int
    updated_count: int
    skipped_count: int
    failed_count: int

