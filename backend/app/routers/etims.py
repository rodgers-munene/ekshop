"""eTIMS / KRA e-invoicing endpoints."""

import uuid
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models.etims import (
    EtimsInvoice, EtimsInvoiceItem, EtimsCreditNote, EtimsCreditNoteItem, EtimsQueue,
    EtimsInvoiceStatus, EtimsDocumentType, EtimsQueueStatus,
)
from app.schemas.etims import (
    EtimsInvoiceRead, EtimsInvoiceItemRead, EtimsCreditNoteRead, EtimsCreditNoteItemRead,
    EtimsQueueRead, EtimsQueueListResponse,
)
from app.services import etims as etims_service

router = APIRouter(prefix="/etims", tags=["etims"])


@router.get("/invoices", response_model=List[EtimsInvoiceRead])
def list_invoices(
    status: Optional[EtimsInvoiceStatus] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """List eTIMS invoices with optional status filter."""
    query = db.query(EtimsInvoice)
    if status:
        query = query.filter(EtimsInvoice.status == status)
    query = query.order_by(EtimsInvoice.created_at.desc())
    total = query.count()
    skip = (page - 1) * limit
    return query.offset(skip).limit(limit).all()


@router.get("/invoices/{invoice_id}", response_model=EtimsInvoiceRead)
def get_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Get a single eTIMS invoice with items."""
    invoice = db.get(EtimsInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/invoices/{invoice_id}/submit", response_model=EtimsInvoiceRead)
async def submit_invoice(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Manually trigger eTIMS submission for an invoice."""
    invoice = db.get(EtimsInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == EtimsInvoiceStatus.validated:
        raise HTTPException(status_code=400, detail="Invoice already validated by KRA")

    await etims_service.queue_invoice_submission(db, invoice_id)
    db.refresh(invoice)
    return invoice


@router.get("/invoices/{invoice_id}/items", response_model=List[EtimsInvoiceItemRead])
def get_invoice_items(
    invoice_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Get items for an eTIMS invoice."""
    invoice = db.get(EtimsInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return db.query(EtimsInvoiceItem).filter(EtimsInvoiceItem.invoice_id == invoice_id).all()


@router.get("/credit-notes", response_model=List[EtimsCreditNoteRead])
def list_credit_notes(
    status: Optional[EtimsInvoiceStatus] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """List eTIMS credit notes."""
    query = db.query(EtimsCreditNote)
    if status:
        query = query.filter(EtimsCreditNote.status == status)
    query = query.order_by(EtimsCreditNote.created_at.desc())
    total = query.count()
    skip = (page - 1) * limit
    return query.offset(skip).limit(limit).all()


@router.get("/credit-notes/{cn_id}", response_model=EtimsCreditNoteRead)
def get_credit_note(
    cn_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Get a single eTIMS credit note with items."""
    cn = db.get(EtimsCreditNote, cn_id)
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return cn


@router.post("/credit-notes/{cn_id}/submit", response_model=EtimsCreditNoteRead)
async def submit_credit_note(
    cn_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Manually trigger eTIMS submission for a credit note."""
    cn = db.get(EtimsCreditNote, cn_id)
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")
    if cn.status == EtimsInvoiceStatus.validated:
        raise HTTPException(status_code=400, detail="Credit note already validated by KRA")

    await etims_service.queue_credit_note_submission(db, cn_id)
    db.refresh(cn)
    return cn


@router.get("/credit-notes/{cn_id}/items", response_model=List[EtimsCreditNoteItemRead])
def get_credit_note_items(
    cn_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Get items for an eTIMS credit note."""
    cn = db.get(EtimsCreditNote, cn_id)
    if not cn:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return db.query(EtimsCreditNoteItem).filter(EtimsCreditNoteItem.credit_note_id == cn_id).all()


@router.get("/queue", response_model=EtimsQueueListResponse)
def list_queue(
    status: Optional[EtimsQueueStatus] = Query(None),
    document_type: Optional[EtimsDocumentType] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """List eTIMS submission queue."""
    query = db.query(EtimsQueue)
    if status:
        query = query.filter(EtimsQueue.status == status)
    if document_type:
        query = query.filter(EtimsQueue.document_type == document_type)
    query = query.order_by(
        EtimsQueue.priority.desc(),
        EtimsQueue.created_at.asc(),
    )
    total = query.count()
    skip = (page - 1) * limit
    items = query.offset(skip).limit(limit).all()
    return EtimsQueueListResponse(total=total, page=page, limit=limit, results=items)


@router.post("/queue/process")
async def process_queue(
    batch_size: int = Query(settings.ETIMS_QUEUE_BATCH_SIZE, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Manually trigger eTIMS queue processing."""
    if not settings.ETIMS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eTIMS integration is not enabled"
        )

    processed = await etims_service.process_queue_batch(db, batch_size)
    return {"processed": processed, "batch_size": batch_size}


@router.post("/invoices/from-order/{order_group_id}", response_model=EtimsInvoiceRead)
def create_invoice_from_order(
    order_group_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Create an eTIMS invoice from a paid order group."""
    from app.models.commerce import OrderGroup
    order_group = db.get(OrderGroup, order_group_id)
    if not order_group:
        raise HTTPException(status_code=404, detail="Order group not found")
    if order_group.status.value != "paid":
        raise HTTPException(status_code=400, detail="Order group is not paid")

    # Check if invoice already exists
    existing = db.query(EtimsInvoice).filter(
        EtimsInvoice.order_group_id == order_group_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="eTIMS invoice already exists for this order")

    try:
        invoice = etims_service.create_etims_invoice_from_order(db, order_group)
        return invoice
    except etims_service.EtimsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/credit-notes/from-return/{return_request_id}", response_model=EtimsCreditNoteRead)
def create_credit_note_from_return(
    return_request_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Create an eTIMS credit note from a return request."""
    try:
        credit_note = etims_service.create_credit_note_from_return(db, return_request_id)
        return credit_note
    except etims_service.EtimsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/config")
def get_etims_config(_: dict = Depends(require_admin)):
    """Get eTIMS configuration status (admin only)."""
    return {
        "enabled": settings.ETIMS_ENABLED,
        "base_url": settings.ETIMS_URL,
        "tin_configured": bool(settings.ETIMS_TIN),
        "device_id_configured": bool(settings.ETIMS_DEVICE_ID),
        "credentials_configured": bool(settings.ETIMS_CLIENT_ID and settings.ETIMS_CLIENT_SECRET),
        "queue_batch_size": settings.ETIMS_QUEUE_BATCH_SIZE,
        "queue_retry_delay": settings.ETIMS_QUEUE_RETRY_DELAY_SECONDS,
        "queue_max_retries": settings.ETIMS_QUEUE_MAX_RETRIES,
    }