"""eTIMS / KRA integration service.

Implements the queue-on-failure pattern for KRA eTIMS submission.
"""

import logging
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func, select, and_

from app.core.config import settings
from app.models.etims import (
    EtimsInvoice, EtimsInvoiceItem, EtimsCreditNote, EtimsCreditNoteItem, EtimsQueue,
    EtimsInvoiceStatus, EtimsDocumentType, EtimsQueueStatus,
)
from app.models.commerce import OrderGroup, Order, OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.models.delivery import DeliveryAgent

logger = logging.getLogger(__name__)

# KRA eTIMS API endpoints
ETIMS_API_LOGIN = "/api/v1/auth/login"
ETIMS_API_INVOICE = "/api/v1/invoices"
ETIMS_API_CREDIT_NOTE = "/api/v1/credit-notes"
ETIMS_API_VALIDATE = "/api/v1/validate"


class EtimsError(Exception):
    """eTIMS integration error."""
    pass


class EtimsClient:
    """Low-level HTTP client for KRA eTIMS API."""

    def __init__(self):
        self.base_url = settings.ETIMS_URL.rstrip("/")
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get_token(self) -> str:
        """Get or refresh OAuth token."""
        if self._token and self._token_expires and datetime.now(timezone.utc) < self._token_expires:
            return self._token

        if not (settings.ETIMS_CLIENT_ID and settings.ETIMS_CLIENT_SECRET):
            raise EtimsError("eTIMS credentials not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}{ETIMS_API_LOGIN}",
                json={
                    "client_id": settings.ETIMS_CLIENT_ID,
                    "client_secret": settings.ETIMS_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            # Assume 1-hour expiry, refresh 5 min early
            self._token_expires = datetime.now(timezone.utc) + timedelta(minutes=55)
            return self._token

    async def _request(self, method: str, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        token = await self._get_token()
        headers = self._headers()
        headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=headers,
                json=payload,
            )
            if resp.status_code >= 400:
                raise EtimsError(f"KRA API error {resp.status_code}: {resp.text}")
            return resp.json()

    async def submit_invoice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit an invoice to KRA eTIMS."""
        return await self._request("POST", ETIMS_API_INVOICE, payload)

    async def submit_credit_note(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a credit note to KRA eTIMS."""
        return await self._request("POST", ETIMS_API_CREDIT_NOTE, payload)


def build_invoice_payload(invoice: EtimsInvoice, items: List[EtimsInvoiceItem]) -> Dict[str, Any]:
    """Build the KRA eTIMS invoice payload from our model."""
    return {
        "documentType": invoice.invoice_type,
        "sellerDetails": {
            "tin": invoice.seller_tin,
            "name": invoice.seller_name,
            "address": invoice.seller_address,
            "deviceId": invoice.seller_device_id,
        },
        "buyerDetails": {
            "tin": invoice.buyer_tin,
            "name": invoice.buyer_name,
            "address": invoice.buyer_address,
        },
        "invoiceDate": invoice.invoice_date.isoformat(),
        "currency": invoice.currency,
        "exchangeRate": str(invoice.exchange_rate),
        "items": [
            {
                "itemCode": item.item_code or "",
                "itemName": item.item_name,
                "description": item.item_description or "",
                "quantity": str(item.quantity),
                "unitOfMeasure": item.unit_of_measure,
                "unitPrice": str(item.unit_price),
                "discountAmount": str(item.discount_amount),
                "taxRate": str(item.tax_rate),
                "taxAmount": str(item.tax_amount),
                "lineTotal": str(item.line_total),
                "hsCode": item.hs_code or "",
                "taxCategory": item.tax_category,
            }
            for item in items
        ],
        "subtotal": str(invoice.subtotal),
        "taxAmount": str(invoice.tax_amount),
        "discountAmount": str(invoice.discount_amount),
        "deliveryFee": str(invoice.delivery_fee),
        "total": str(invoice.total),
        "vatBreakdown": invoice.vat_breakdown or [],
    }


def build_credit_note_payload(
    credit_note: EtimsCreditNote,
    items: List[EtimsCreditNoteItem],
    original_invoice: EtimsInvoice,
) -> Dict[str, Any]:
    """Build the KRA eTIMS credit note payload from our model."""
    return {
        "documentType": "credit_note",
        "originalInvoice": {
            "cuInvoiceNumber": original_invoice.cu_invoice_number,
            "cuSerialNumber": original_invoice.cu_serial_number,
        },
        "sellerDetails": {
            "tin": original_invoice.seller_tin,
            "name": original_invoice.seller_name,
            "address": original_invoice.seller_address,
            "deviceId": original_invoice.seller_device_id,
        },
        "buyerDetails": {
            "tin": original_invoice.buyer_tin,
            "name": original_invoice.buyer_name,
            "address": original_invoice.buyer_address,
        },
        "creditNoteDate": datetime.now(timezone.utc).isoformat(),
        "reason": credit_note.reason,
        "reasonDetail": credit_note.reason_detail or "",
        "currency": credit_note.currency,
        "items": [
            {
                "itemName": item.item_name,
                "quantity": str(item.quantity),
                "unitOfMeasure": item.unit_of_measure,
                "unitPrice": str(item.unit_price),
                "taxRate": str(item.tax_rate),
                "taxAmount": str(item.tax_amount),
                "lineTotal": str(item.line_total),
            }
            for item in items
        ],
        "totalAmount": str(credit_note.total_amount),
        "taxAmount": str(credit_note.tax_amount),
    }


async def queue_invoice_submission(db: Session, invoice_id: uuid.UUID) -> None:
    """Queue an eTIMS invoice for submission (called after payment confirmation)."""
    invoice = db.get(EtimsInvoice, invoice_id)
    if not invoice:
        raise EtimsError(f"Invoice {invoice_id} not found")

    items = db.query(EtimsInvoiceItem).filter(EtimsInvoiceItem.invoice_id == invoice_id).all()
    payload = build_invoice_payload(invoice, items)

    queue = EtimsQueue(
        document_type=EtimsDocumentType.invoice,
        document_id=invoice_id,
        payload=payload,
        priority=10,  # High priority for new invoices
    )
    db.add(queue)
    db.commit()


async def queue_credit_note_submission(db: Session, credit_note_id: uuid.UUID) -> None:
    """Queue an eTIMS credit note for submission (called after refund/return)."""
    credit_note = db.get(EtimsCreditNote, credit_note_id)
    if not credit_note:
        raise EtimsError(f"Credit note {credit_note_id} not found")

    original_invoice = db.get(EtimsInvoice, credit_note.original_invoice_id)
    if not original_invoice:
        raise EtimsError(f"Original invoice {credit_note.original_invoice_id} not found")

    items = db.query(EtimsCreditNoteItem).filter(
        EtimsCreditNoteItem.credit_note_id == credit_note_id
    ).all()
    payload = build_credit_note_payload(credit_note, items, original_invoice)

    queue = EtimsQueue(
        document_type=EtimsDocumentType.credit_note,
        document_id=credit_note_id,
        payload=payload,
        priority=5,  # Normal priority
    )
    db.add(queue)
    db.commit()


async def process_queue_batch(db: Session, batch_size: Optional[int] = None) -> int:
    """Process pending eTIMS queue items. Returns number of items processed."""
    if not settings.ETIMS_ENABLED:
        return 0

    batch_size = batch_size or settings.ETIMS_QUEUE_BATCH_SIZE
    client = EtimsClient()
    processed = 0

    # Get pending items ordered by priority (desc) then created_at (asc)
    queue_items = db.query(EtimsQueue).filter(
        EtimsQueue.status == EtimsQueueStatus.pending,
        EtimsQueue.next_retry_at.is_(None) | (EtimsQueue.next_retry_at <= datetime.now(timezone.utc)),
    ).order_by(
        EtimsQueue.priority.desc(),
        EtimsQueue.created_at.asc(),
    ).limit(batch_size).all()

    for item in queue_items:
        try:
            item.status = EtimsQueueStatus.processing
            item.attempt += 1
            db.commit()

            if item.document_type == EtimsDocumentType.invoice:
                result = await client.submit_invoice(item.payload)
            elif item.document_type == EtimsDocumentType.credit_note:
                result = await client.submit_credit_note(item.payload)
            else:
                raise EtimsError(f"Unknown document type: {item.document_type}")

            # On success, update the source document with KRA response
            if item.document_type == EtimsDocumentType.invoice:
                invoice = db.get(EtimsInvoice, item.document_id)
                if invoice:
                    invoice.cu_invoice_number = result.get("cuInvoiceNumber")
                    invoice.cu_serial_number = result.get("cuSerialNumber")
                    invoice.kra_qr_code = result.get("qrCode")
                    invoice.kra_signature = result.get("signature")
                    invoice.kra_validation_timestamp = datetime.now(timezone.utc)
                    invoice.status = EtimsInvoiceStatus.validated
                    invoice.validated_at = datetime.now(timezone.utc)
            else:
                credit_note = db.get(EtimsCreditNote, item.document_id)
                if credit_note:
                    credit_note.cu_credit_note_number = result.get("cuCreditNoteNumber")
                    credit_note.cu_serial_number = result.get("cuSerialNumber")
                    credit_note.kra_qr_code = result.get("qrCode")
                    credit_note.kra_signature = result.get("signature")
                    credit_note.kra_validation_timestamp = datetime.now(timezone.utc)
                    credit_note.status = EtimsInvoiceStatus.validated
                    credit_note.validated_at = datetime.now(timezone.utc)

            item.status = EtimsQueueStatus.completed
            item.completed_at = datetime.now(timezone.utc)
            processed += 1

        except EtimsError as e:
            item.last_error = str(e)
            if item.attempt >= item.max_attempts:
                item.status = EtimsQueueStatus.dead_letter
            else:
                item.status = EtimsQueueStatus.pending
                # Exponential backoff
                delay = settings.ETIMS_QUEUE_RETRY_DELAY_SECONDS * (2 ** (item.attempt - 1))
                item.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            logger.warning(f"eTIMS submission failed for {item.id}: {e}")

        except Exception as e:
            item.last_error = f"Unexpected error: {e}"
            if item.attempt >= item.max_attempts:
                item.status = EtimsQueueStatus.dead_letter
            else:
                item.status = EtimsQueueStatus.pending
                delay = settings.ETIMS_QUEUE_RETRY_DELAY_SECONDS * (2 ** (item.attempt - 1))
                item.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            logger.exception(f"Unexpected error processing eTIMS queue {item.id}")

        db.commit()

    return processed


def create_etims_invoice_from_order(db: Session, order_group: OrderGroup) -> EtimsInvoice:
    """Create an eTIMS invoice record from a paid order group."""
    # Get payment info
    payment = db.query(Payment).filter(
        Payment.order_group_id == order_group.id,
        Payment.status == "success",
    ).first()

    # Get buyer details
    buyer = db.get(User, order_group.buyer_id)
    if not buyer:
        raise EtimsError(f"Buyer {order_group.buyer_id} not found")

    # Get first shop for seller details (assuming single-shop order group)
    first_order = db.query(Order).filter(Order.group_id == order_group.id).first()
    if not first_order:
        raise EtimsError(f"No orders in group {order_group.id}")

    shop = db.get(first_order.shop)
    if not shop:
        raise EtimsError(f"Shop {first_order.shop_id} not found")

    seller = db.get(User, shop.seller_id)
    if not seller:
        raise EtimsError(f"Seller {shop.seller_id} not found")

    # Build invoice
    invoice = EtimsInvoice(
        order_group_id=order_group.id,
        payment_id=payment.id if payment else None,
        seller_tin=seller.kra_pin or settings.ETIMS_TIN or "UNKNOWN",
        seller_name=seller.first_name + " " + seller.last_name,
        seller_address=seller.county or "Kenya",
        seller_device_id=settings.ETIMS_DEVICE_ID or "UNKNOWN",
        buyer_tin=buyer.kra_pin,
        buyer_name=buyer.first_name + " " + buyer.last_name,
        buyer_address=(
            f"{order_group.delivery_address.get('exact_location', '')}, "
            f"{order_group.delivery_address.get('town', '')}, "
            f"{order_group.delivery_address.get('county', '')}"
        ).strip(", "),
        invoice_date=datetime.now(timezone.utc),
        currency="KES",
        subtotal=order_group.subtotal or "0.00",
        tax_amount=order_group.tax_amount or "0.00",
        delivery_fee=order_group.delivery_fee or "0.00",
        total=order_group.total or "0.00",
        status=EtimsInvoiceStatus.pending,
    )
    db.add(invoice)
    db.flush()

    # Create items
    for order in order_group.orders:
        for oi in order.items:
            item = EtimsInvoiceItem(
                invoice_id=invoice.id,
                order_item_id=oi.id,
                item_code=oi.product_snapshot.get("sku") if oi.product_snapshot else None,
                item_name=oi.product_snapshot.get("name", "Product") if oi.product_snapshot else "Product",
                item_description=oi.product_snapshot.get("description") if oi.product_snapshot else None,
                quantity=oi.quantity,
                unit_of_measure="pcs",
                unit_price=str(oi.unit_price),
                discount_amount=str(oi.discount_amount or "0.00"),
                tax_rate=oi.tax_rate or 0.16,
                tax_amount=str(oi.tax_amount or "0.00"),
                line_total=str(oi.line_total),
                hs_code=oi.product_snapshot.get("hs_code") if oi.product_snapshot else None,
                tax_category="standard" if (oi.tax_rate or 0) > 0 else "exempt",
            )
            db.add(item)

    # Build VAT breakdown
    vat_rates = {}
    for order in order_group.orders:
        for oi in order.items:
            rate = float(oi.tax_rate or 0.16)
            if rate not in vat_rates:
                vat_rates[rate] = {"taxable": Decimal("0"), "tax": Decimal("0")}
            taxable = Decimal(str(oi.line_total)) - Decimal(str(oi.tax_amount or "0"))
            tax = Decimal(str(oi.tax_amount or "0"))
            vat_rates[rate]["taxable"] += taxable
            vat_rates[rate]["tax"] += tax

    invoice.vat_breakdown = [
        {"rate": str(rate), "taxable": str(v["taxable"]), "tax": str(v["tax"])}
        for rate, v in vat_rates.items()
    ]

    db.commit()
    db.refresh(invoice)
    return invoice


def create_credit_note_from_return(db: Session, return_request_id: uuid.UUID) -> EtimsCreditNote:
    """Create an eTIMS credit note from a return request."""
    from app.models.commerce import ReturnRequest

    return_req = db.get(ReturnRequest, return_request_id)
    if not return_req:
        raise EtimsError(f"Return request {return_request_id} not found")

    order_group = db.get(OrderGroup, return_req.order_id)
    if not order_group:
        raise EtimsError(f"Order group {return_req.order_id} not found")

    original_invoice = db.query(EtimsInvoice).filter(
        EtimsInvoice.order_group_id == order_group.id
    ).first()
    if not original_invoice:
        raise EtimsError(f"No eTIMS invoice for order group {order_group.id}")

    credit_note = EtimsCreditNote(
        original_invoice_id=original_invoice.id,
        order_group_id=order_group.id,
        return_request_id=return_request_id,
        original_cu_invoice_number=original_invoice.cu_invoice_number or "UNKNOWN",
        original_cu_serial_number=original_invoice.cu_serial_number or "UNKNOWN",
        reason="return",
        reason_detail=return_req.reason_detail,
        total_amount=str(return_req.refund_amount or "0.00"),
        tax_amount=str(return_req.tax_amount or "0.00"),
        currency="KES",
        status=EtimsInvoiceStatus.pending,
    )
    db.add(credit_note)
    db.flush()

    # Create credit note items
    for return_item in return_req.items:
        item = EtimsCreditNoteItem(
            credit_note_id=credit_note.id,
            item_name=return_item.product_name,
            quantity=return_item.quantity,
            unit_of_measure="pcs",
            unit_price=str(return_item.unit_price),
            tax_rate=0.16,
            tax_amount=str(Decimal(str(return_item.unit_price)) * Decimal("0.16") * Decimal(str(return_item.quantity))),
            line_total=str(Decimal(str(return_item.unit_price)) * Decimal(str(return_item.quantity))),
        )
        db.add(item)

    db.commit()
    db.refresh(credit_note)
    return credit_note