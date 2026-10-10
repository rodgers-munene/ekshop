"""eTIMS / KRA models for electronic tax invoice management."""

import uuid
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column, String, Text, DateTime, Enum, ForeignKey, Index, Numeric, Boolean, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class EtimsInvoiceStatus(str, enum.Enum):
    """Status of an eTIMS invoice in the KRA system."""
    pending = "pending"           # Queued for submission
    submitted = "submitted"       # Sent to KRA, awaiting response
    validated = "validated"       # KRA accepted, CU number + QR assigned
    rejected = "rejected"         # KRA rejected (validation errors)
    cancelled = "cancelled"       # Cancelled via credit note


class EtimsDocumentType(str, enum.Enum):
    """Type of eTIMS document."""
    invoice = "invoice"
    credit_note = "credit_note"
    debit_note = "debit_note"


class EtimsQueueStatus(str, enum.Enum):
    """Status of an item in the eTIMS submission queue."""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    dead_letter = "dead_letter"  # Max retries exceeded


class EtimsInvoice(Base):
    """
    eTIMS invoice record linking an OrderGroup to its KRA submission.
    
    One OrderGroup can have at most one validated eTIMS invoice.
    If the invoice is rejected, a new attempt creates a new EtimsInvoice row.
    """
    __tablename__ = "etims_invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_group_id = Column(UUID(as_uuid=True), ForeignKey("order_groups.id", ondelete="RESTRICT"), nullable=False, unique=True)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)

    # KRA-assigned fields (populated on validation)
    cu_invoice_number = Column(String(50), unique=True, nullable=True)     # Control Unit invoice number
    cu_serial_number = Column(String(50), nullable=True)                   # CU serial number
    kra_qr_code = Column(Text, nullable=True)                              # Base64 or URL to QR code
    kra_signature = Column(Text, nullable=True)                            # KRA digital signature/hash
    kra_validation_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Seller details (snapshotted at submission time)
    seller_tin = Column(String(20), nullable=False)
    seller_name = Column(String(200), nullable=False)
    seller_address = Column(Text, nullable=False)
    seller_device_id = Column(String(50), nullable=False)                  # CU device ID

    # Buyer details
    buyer_tin = Column(String(20), nullable=True)                          # Optional for B2C
    buyer_name = Column(String(200), nullable=False)
    buyer_address = Column(Text, nullable=False)

    # Invoice details
    invoice_date = Column(DateTime(timezone=True), nullable=False)
    invoice_type = Column(Enum(EtimsDocumentType, native_enum=False), default=EtimsDocumentType.invoice, nullable=False)
    currency = Column(String(3), default="KES", nullable=False)
    exchange_rate = Column(Numeric(10, 6), default=1.0, nullable=False)    # For foreign currency

    # Totals
    subtotal = Column(String(20), nullable=False)
    tax_amount = Column(String(20), default="0.00", nullable=False)
    discount_amount = Column(String(20), default="0.00", nullable=False)
    delivery_fee = Column(String(20), default="0.00", nullable=False)
    total = Column(String(20), nullable=False)

    # VAT breakdown (JSON for flexibility)
    vat_breakdown = Column(JSON, nullable=True)  # [{"rate": 0.16, "taxable": "1000", "tax": "160"}, ...]

    # Status tracking
    status = Column(Enum(EtimsInvoiceStatus, native_enum=False), default=EtimsInvoiceStatus.pending, nullable=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Numeric(3), default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    order_group = relationship("OrderGroup", back_populates="etims_invoice")
    items = relationship("EtimsInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    credit_notes = relationship("EtimsCreditNote", foreign_keys="EtimsCreditNote.original_invoice_id", back_populates="original_invoice")

    __table_args__ = (
        Index("ix_etims_invoices_order_group_id", "order_group_id"),
        Index("ix_etims_invoices_cu_invoice_number", "cu_invoice_number"),
        Index("ix_etims_invoices_status", "status"),
        Index("ix_etims_invoices_created_at", "created_at"),
    )


class EtimsInvoiceItem(Base):
    """Line items on an eTIMS invoice."""
    __tablename__ = "etims_invoice_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("etims_invoices.id", ondelete="CASCADE"), nullable=False)
    order_item_id = Column(UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True)

    # Item details (snapshotted)
    item_code = Column(String(50), nullable=True)          # HS code / product code
    item_name = Column(String(200), nullable=False)
    item_description = Column(Text, nullable=True)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_of_measure = Column(String(20), default="pcs", nullable=False)
    unit_price = Column(String(20), nullable=False)
    discount_amount = Column(String(20), default="0.00", nullable=False)
    tax_rate = Column(Numeric(5, 4), default=0.16, nullable=False)  # e.g., 0.16 for 16%
    tax_amount = Column(String(20), default="0.00", nullable=False)
    line_total = Column(String(20), nullable=False)        # (unit_price * qty) - discount + tax

    # HS / Tax category
    hs_code = Column(String(20), nullable=True)            # Harmonized System code
    tax_category = Column(String(20), default="standard", nullable=False)  # standard, zero_rated, exempt

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = relationship("EtimsInvoice", back_populates="items")

    __table_args__ = (
        Index("ix_etims_invoice_items_invoice_id", "invoice_id"),
        Index("ix_etims_invoice_items_order_item_id", "order_item_id"),
    )


class EtimsCreditNote(Base):
    """
    eTIMS Credit Note for returns/refunds.
    
    References the original EtimsInvoice via cu_invoice_number and cu_serial_number.
    """
    __tablename__ = "etims_credit_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_invoice_id = Column(UUID(as_uuid=True), ForeignKey("etims_invoices.id", ondelete="RESTRICT"), nullable=False)
    order_group_id = Column(UUID(as_uuid=True), ForeignKey("order_groups.id", ondelete="RESTRICT"), nullable=False)
    return_request_id = Column(UUID(as_uuid=True), ForeignKey("return_requests.id", ondelete="SET NULL"), nullable=True)

    # KRA-assigned fields
    cu_credit_note_number = Column(String(50), unique=True, nullable=True)
    cu_serial_number = Column(String(50), nullable=True)
    kra_qr_code = Column(Text, nullable=True)
    kra_signature = Column(Text, nullable=True)
    kra_validation_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Original invoice reference (required by KRA)
    original_cu_invoice_number = Column(String(50), nullable=False)
    original_cu_serial_number = Column(String(50), nullable=False)

    # Reason
    reason = Column(String(100), nullable=False)  # return, discount, error_correction
    reason_detail = Column(Text, nullable=True)

    # Totals
    total_amount = Column(String(20), nullable=False)
    tax_amount = Column(String(20), default="0.00", nullable=False)
    currency = Column(String(3), default="KES", nullable=False)

    # Status
    status = Column(Enum(EtimsInvoiceStatus, native_enum=False), default=EtimsInvoiceStatus.pending, nullable=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Numeric(3), default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)

    original_invoice = relationship("EtimsInvoice", foreign_keys=[original_invoice_id], back_populates="credit_notes")
    items = relationship("EtimsCreditNoteItem", back_populates="credit_note", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_etims_credit_notes_original_invoice_id", "original_invoice_id"),
        Index("ix_etims_credit_notes_order_group_id", "order_group_id"),
        Index("ix_etims_credit_notes_cu_credit_note_number", "cu_credit_note_number"),
        Index("ix_etims_credit_notes_status", "status"),
    )


class EtimsCreditNoteItem(Base):
    """Line items on an eTIMS credit note."""
    __tablename__ = "etims_credit_note_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    credit_note_id = Column(UUID(as_uuid=True), ForeignKey("etims_credit_notes.id", ondelete="CASCADE"), nullable=False)
    original_invoice_item_id = Column(UUID(as_uuid=True), ForeignKey("etims_invoice_items.id", ondelete="SET NULL"), nullable=True)

    item_name = Column(String(200), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_of_measure = Column(String(20), default="pcs", nullable=False)
    unit_price = Column(String(20), nullable=False)
    tax_rate = Column(Numeric(5, 4), default=0.16, nullable=False)
    tax_amount = Column(String(20), default="0.00", nullable=False)
    line_total = Column(String(20), nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    credit_note = relationship("EtimsCreditNote", back_populates="items")

    __table_args__ = (
        Index("ix_etims_credit_note_items_credit_note_id", "credit_note_id"),
    )


class EtimsQueue(Base):
    """
    Outbox queue for eTIMS document submission.
    
    Implements the "queue on failure" pattern: when KRA is unreachable,
    documents are queued and retried by a background worker.
    """
    __tablename__ = "etims_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type = Column(Enum(EtimsDocumentType, native_enum=False), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)  # etims_invoices.id or etims_credit_notes.id

    payload = Column(JSON, nullable=False)  # Full payload for KRA API
    priority = Column(Numeric(2), default=0, nullable=False)  # Higher = more urgent

    status = Column(Enum(EtimsQueueStatus, native_enum=False), default=EtimsQueueStatus.pending, nullable=False)
    attempt = Column(Numeric(3), default=0, nullable=False)
    max_attempts = Column(Numeric(3), default=10, nullable=False)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_etims_queue_status_priority", "status", "priority"),
        Index("ix_etims_queue_next_retry_at", "next_retry_at"),
        Index("ix_etims_queue_document", "document_type", "document_id"),
    )