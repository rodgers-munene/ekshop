"""eTIMS / KRA e-invoicing schemas."""

import uuid
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# ---- Invoice Items ----

class EtimsInvoiceItemRead(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    order_item_id: Optional[uuid.UUID] = None
    item_code: Optional[str] = None
    item_name: str
    item_description: Optional[str] = None
    quantity: Decimal
    unit_of_measure: str
    unit_price: str
    discount_amount: str
    tax_rate: Decimal
    tax_amount: str
    line_total: str
    hs_code: Optional[str] = None
    tax_category: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EtimsInvoiceItemCreate(BaseModel):
    item_code: Optional[str] = None
    item_name: str
    item_description: Optional[str] = None
    quantity: Decimal
    unit_of_measure: str = "pcs"
    unit_price: str
    discount_amount: str = "0.00"
    tax_rate: Decimal = Decimal("0.16")
    tax_amount: str = "0.00"
    line_total: str
    hs_code: Optional[str] = None
    tax_category: str = "standard"


# ---- Invoices ----

class EtimsInvoiceRead(BaseModel):
    id: uuid.UUID
    order_group_id: uuid.UUID
    payment_id: Optional[uuid.UUID] = None
    cu_invoice_number: Optional[str] = None
    cu_serial_number: Optional[str] = None
    kra_qr_code: Optional[str] = None
    kra_signature: Optional[str] = None
    kra_validation_timestamp: Optional[datetime] = None
    seller_tin: str
    seller_name: str
    seller_address: str
    seller_device_id: str
    buyer_tin: Optional[str] = None
    buyer_name: str
    buyer_address: str
    invoice_date: datetime
    invoice_type: str
    currency: str
    exchange_rate: Decimal
    subtotal: str
    tax_amount: str
    discount_amount: str
    delivery_fee: str
    total: str
    vat_breakdown: Optional[List[dict]] = None
    status: str
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    items: List[EtimsInvoiceItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class EtimsInvoiceCreate(BaseModel):
    order_group_id: uuid.UUID
    seller_tin: str
    seller_name: str
    seller_address: str
    seller_device_id: str
    buyer_tin: Optional[str] = None
    buyer_name: str
    buyer_address: str
    invoice_type: str = "invoice"
    currency: str = "KES"
    exchange_rate: Decimal = Decimal("1.0")
    subtotal: str
    tax_amount: str = "0.00"
    discount_amount: str = "0.00"
    delivery_fee: str = "0.00"
    total: str
    items: List[EtimsInvoiceItemCreate]


# ---- Credit Note Items ----

class EtimsCreditNoteItemRead(BaseModel):
    id: uuid.UUID
    credit_note_id: uuid.UUID
    original_invoice_item_id: Optional[uuid.UUID] = None
    item_name: str
    quantity: Decimal
    unit_of_measure: str
    unit_price: str
    tax_rate: Decimal
    tax_amount: str
    line_total: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Credit Notes ----

class EtimsCreditNoteRead(BaseModel):
    id: uuid.UUID
    original_invoice_id: uuid.UUID
    order_group_id: uuid.UUID
    return_request_id: Optional[uuid.UUID] = None
    cu_credit_note_number: Optional[str] = None
    cu_serial_number: Optional[str] = None
    kra_qr_code: Optional[str] = None
    kra_signature: Optional[str] = None
    kra_validation_timestamp: Optional[datetime] = None
    original_cu_invoice_number: str
    original_cu_serial_number: str
    reason: str
    reason_detail: Optional[str] = None
    total_amount: str
    tax_amount: str
    currency: str
    status: str
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    items: List[EtimsCreditNoteItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class EtimsCreditNoteCreate(BaseModel):
    original_invoice_id: uuid.UUID
    order_group_id: uuid.UUID
    return_request_id: Optional[uuid.UUID] = None
    original_cu_invoice_number: str
    original_cu_serial_number: str
    reason: str
    reason_detail: Optional[str] = None
    total_amount: str
    tax_amount: str = "0.00"
    currency: str = "KES"
    items: List[EtimsInvoiceItemCreate]


# ---- Queue ----

class EtimsQueueRead(BaseModel):
    id: uuid.UUID
    document_type: str
    document_id: uuid.UUID
    payload: dict
    priority: int
    status: str
    attempt: int
    max_attempts: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    next_retry_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EtimsQueueListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[EtimsQueueRead]