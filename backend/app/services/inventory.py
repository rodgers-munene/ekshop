"""Inventory reservation service with TTL (time-to-live) for checkout holds."""

import logging
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.catalog import Product, ProductVariant

logger = logging.getLogger(__name__)

# Default reservation TTL: 10 minutes (covers typical checkout flow)
DEFAULT_RESERVATION_TTL_MINUTES = 10


class InventoryReservation:
    """Manages temporary stock reservations during checkout."""

    def __init__(self, db: Session, ttl_minutes: int = DEFAULT_RESERVATION_TTL_MINUTES):
        self.db = db
        self.ttl = timedelta(minutes=ttl_minutes)

    def _available_qty(self, product: Product, variant: Optional[ProductVariant] = None) -> int:
        """Calculate available quantity (stock - reserved)."""
        if variant:
            return variant.stock_qty - variant.reserved_qty
        return product.stock_qty - product.reserved_qty

    def reserve(
        self,
        product_id: uuid.UUID,
        quantity: int,
        variant_id: Optional[uuid.UUID] = None,
        ttl_minutes: Optional[int] = None,
    ) -> bool:
        """Reserve quantity for a product/variant. Returns True if successful."""
        if quantity <= 0:
            return False

        if variant_id:
            variant = self.db.query(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product_id,
            ).first()
            if not variant:
                return False
            available = variant.stock_qty - variant.reserved_qty
            if available < quantity:
                return False
            variant.reserved_qty += quantity
            self.db.add(variant)
        else:
            product = self.db.query(Product).filter(Product.id == product_id).first()
            if not product:
                return False
            available = product.stock_qty - product.reserved_qty
            if available < quantity:
                return False
            product.reserved_qty += quantity
            self.db.add(product)

        self.db.commit()
        return True

    def release(
        self,
        product_id: uuid.UUID,
        quantity: int,
        variant_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Release a previously held reservation."""
        if quantity <= 0:
            return False

        if variant_id:
            variant = self.db.query(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product_id,
            ).first()
            if not variant:
                return False
            variant.reserved_qty = max(0, variant.reserved_qty - quantity)
            self.db.add(variant)
        else:
            product = self.db.query(Product).filter(Product.id == product_id).first()
            if not product:
                return False
            product.reserved_qty = max(0, product.reserved_qty - quantity)
            self.db.add(product)

        self.db.commit()
        return True

    def confirm(
        self,
        product_id: uuid.UUID,
        quantity: int,
        variant_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Convert reservation to confirmed sale (decrement stock, release reservation)."""
        if quantity <= 0:
            return False

        if variant_id:
            variant = self.db.query(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product_id,
            ).first()
            if not variant:
                return False
            if variant.stock_qty < quantity:
                return False
            variant.stock_qty -= quantity
            variant.reserved_qty = max(0, variant.reserved_qty - quantity)
            self.db.add(variant)
        else:
            product = self.db.query(Product).filter(Product.id == product_id).first()
            if not product:
                return False
            if product.stock_qty < quantity:
                return False
            product.stock_qty -= quantity
            product.reserved_qty = max(0, product.reserved_qty - quantity)
            self.db.add(product)

        self.db.commit()
        return True

    def get_available(self, product_id: uuid.UUID, variant_id: Optional[uuid.UUID] = None) -> int:
        """Get currently available quantity (stock - reserved)."""
        if variant_id:
            variant = self.db.query(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product_id,
            ).first()
            if not variant:
                return 0
            return variant.stock_qty - variant.reserved_qty
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return 0
        return product.stock_qty - product.reserved_qty

    def cleanup_expired_reservations(self) -> int:
        """
        Clean up reservations older than TTL.
        Note: This requires a timestamp column on reservations to work properly.
        For now, this is a placeholder for a more sophisticated implementation
        that would track reservation creation timestamps.
        """
        # In a production system, you'd track reservation timestamps
        # and have a cron job that releases expired reservations.
        # For now, we don't have timestamp tracking on the reserved_qty columns.
        return 0