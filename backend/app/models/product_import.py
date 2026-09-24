import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, Enum, ForeignKey, Integer, Text, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ImportStatus(str, enum.Enum):
    parsing = "parsing"
    ready = "ready"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ImportRowStatus(str, enum.Enum):
    # set while parsing
    valid = "valid"        # staged, waiting to be committed
    invalid = "invalid"    # defective row, never committed (see .error)
    # set while committing
    created = "created"
    updated = "updated"
    skipped = "skipped"    # matched an existing product, seller chose to skip
    failed = "failed"


class DuplicateAction(str, enum.Enum):
    """What to do with a row whose Code already exists in the shop.

    The common case isn't a mistake, it's a re-upload of a refreshed stock
    export, so the default updates price and stock and leaves everything the
    seller has since edited — name, description, images, category — alone.
    """
    skip = "skip"
    update_stock_price = "update_stock_price"
    create_new = "create_new"


class ProductImport(Base):
    __tablename__ = "product_imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    status = Column(
        Enum(ImportStatus, native_enum=False, length=32),
        default=ImportStatus.parsing,
        nullable=False,
    )

    # Every product in one import lands in the same category: the spreadsheet's
    # "Brand" column is a supplier grouping (a mix of real brands, product types
    # and hybrids like "FACE CARE - NIVEA"), so it can't drive categories. It
    # goes to Product.tags instead, where the search trigger already indexes it.
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"))
    on_duplicate = Column(
        Enum(DuplicateAction, native_enum=False, length=32),
        default=DuplicateAction.update_stock_price,
        nullable=False,
    )

    # counted while parsing: total_rows == valid_rows + invalid_rows
    total_rows = Column(Integer, default=0, nullable=False)
    valid_rows = Column(Integer, default=0, nullable=False)
    invalid_rows = Column(Integer, default=0, nullable=False)
    # valid rows already in the shop under this Code. Lets the review screen
    # re-split "new" vs "will update" as the seller flips on_duplicate, without
    # another round trip.
    matched_rows = Column(Integer, default=0, nullable=False)

    # counted while committing
    created_count = Column(Integer, default=0, nullable=False)
    updated_count = Column(Integer, default=0, nullable=False)
    skipped_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)

    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_product_imports_shop_id", "shop_id"),
    )

    shop = relationship("Shop")
    category = relationship("Category")
    rows = relationship(
        "ProductImportRow", back_populates="product_import", cascade="all, delete-orphan"
    )


class ProductImportRow(Base):
    __tablename__ = "product_import_rows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    import_id = Column(
        UUID(as_uuid=True), ForeignKey("product_imports.id", ondelete="CASCADE"), nullable=False
    )
    # the spreadsheet's own row number, so a rejection can be pointed at
    row_number = Column(Integer, nullable=False)
    # the untouched cells. A row that failed to parse has nothing in the typed
    # columns below, so this is the only record of what the seller actually sent.
    raw = Column(JSONB)

    sku = Column(String(100))
    name = Column(String(255))
    price = Column(String(20))
    stock_qty = Column(Integer)
    brand = Column(String(255))

    # resolved while parsing, from (shop_id, sku)
    matched_product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"))
    # what the commit actually created or updated
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"))

    status = Column(
        Enum(ImportRowStatus, native_enum=False, length=32),
        default=ImportRowStatus.valid,
        nullable=False,
    )
    error = Column(Text)

    __table_args__ = (
        # the commit loop's only hot query: next batch of `valid` rows
        Index("ix_product_import_rows_import_status", "import_id", "status"),
    )

    product_import = relationship("ProductImport", back_populates="rows")
