import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, Boolean, Enum, ForeignKey,
    Integer, Text, UniqueConstraint, CheckConstraint, Index, Float
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OrderGroupStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    paid = "paid"
    cancelled = "cancelled"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


class ReturnStatus(str, enum.Enum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    received = "received"
    refunded = "refunded"
    cancelled = "cancelled"


class ReturnReason(str, enum.Enum):
    damaged = "damaged"
    wrong_item = "wrong_item"
    not_as_described = "not_as_described"
    changed_mind = "changed_mind"
    defective = "defective"
    late_delivery = "late_delivery"
    other = "other"


class TaxType(str, enum.Enum):
    vat = "vat"
    excise = "excise"
    withholding = "withholding"


class TaxConfig(Base):
    __tablename__ = "tax_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "Kenya VAT"
    tax_type = Column(Enum(TaxType, native_enum=False), nullable=False)
    rate = Column(Float, nullable=False)  # e.g., 0.16 for 16%
    is_active = Column(Boolean, default=True, nullable=False)
    applies_to_shipping = Column(Boolean, default=True, nullable=False)
    country = Column(String(2), default="KE", nullable=False)  # ISO 3166-1 alpha-2
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tax_type", "country", name="uq_tax_config_type_country"),
    )


class UserAddress(Base):
    __tablename__ = "user_addresses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(50))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    county = Column(String(100), nullable=False)
    town = Column(String(100), nullable=False)
    ward_id = Column(UUID(as_uuid=True), ForeignKey("wards.id", ondelete="SET NULL"))
    exact_location = Column(String(255))
    apartment = Column(String(255))
    floor = Column(String(50))
    lat = Column(Float)
    lng = Column(Float)
    sublocation = Column(String(255))
    is_default = Column(Boolean, default=False, nullable=False)
    # Delivery preferences
    delivery_instructions = Column(Text)  # leave at door, call on arrival, etc.
    call_on_arrival = Column(Boolean, default=False)
    leave_at_door = Column(Boolean, default=False)
    require_signature = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="addresses")
    ward = relationship("Ward")


class Cart(Base):
    __tablename__ = "carts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User", back_populates="cart")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id = Column(UUID(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"))
    quantity = Column(Integer, nullable=False, default=1)
    added_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", "variant_id", name="uq_cart_item"),
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity"),
    )

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product", back_populates="cart_items")
    variant = relationship("ProductVariant", back_populates="cart_items")


class Wishlist(Base):
    __tablename__ = "wishlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    added_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),)

    user = relationship("User", back_populates="wishlists")
    product = relationship("Product", back_populates="wishlist_entries")


class OrderGroup(Base):
    __tablename__ = "order_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(Enum(OrderGroupStatus, native_enum=False), default=OrderGroupStatus.pending_payment, nullable=False)
    subtotal = Column(String(20), nullable=False)
    delivery_fee = Column(String(20), default="0.00")
    tax_amount = Column(String(20), default="0.00")
    total = Column(String(20), nullable=False)
    delivery_address = Column(JSONB, nullable=False)
    # Delivery preferences
    delivery_instructions = Column(Text)  # leave at door, call on arrival, etc.
    call_on_arrival = Column(Boolean, default=False)
    leave_at_door = Column(Boolean, default=False)
    require_signature = Column(Boolean, default=False)
    # Scheduled delivery
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    buyer = relationship("User", back_populates="order_groups")
    orders = relationship("Order", back_populates="group", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order_group")
    payment_intents = relationship("PaymentIntent", back_populates="order_group", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("order_groups.id", ondelete="CASCADE"), nullable=False)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id"), nullable=False)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(Enum(OrderStatus, native_enum=False), default=OrderStatus.pending, nullable=False)
    subtotal = Column(String(20), nullable=False)
    delivery_fee = Column(String(20), default="0.00")
    tax_amount = Column(String(20), default="0.00")
    total = Column(String(20), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_orders_buyer_id", "buyer_id"),
        Index("ix_orders_shop_id", "shop_id"),
        Index("ix_orders_status", "status"),
    )

    group = relationship("OrderGroup", back_populates="orders")
    shop = relationship("Shop", back_populates="orders")
    buyer = relationship("User", back_populates="orders", foreign_keys=[buyer_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    # Fulfillment is 1:1 with the order in v1, but declared as a list so
    # item-level grouping can be added without reshaping the schema.
    fulfillments = relationship(
        "Fulfillment", back_populates="order", cascade="all, delete-orphan"
    )
    delivery = relationship("Delivery", back_populates="order", uselist=False)
    return_requests = relationship("ReturnRequest", back_populates="order", cascade="all, delete-orphan")

    @property
    def buyer_name(self) -> str:
        return f"{self.buyer.first_name} {self.buyer.last_name}"

    @property
    def delivery_address(self):
        return self.group.delivery_address


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"))
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"))
    product_snapshot = Column(JSONB, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(String(20), nullable=False)
    discount_amount = Column(String(20), default="0.00")
    tax_amount = Column(String(20), default="0.00")
    tax_rate = Column(Float, default=0.0)
    line_total = Column(String(20), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    variant = relationship("ProductVariant", back_populates="order_items")
    return_items = relationship("ReturnItem", back_populates="order_item", cascade="all, delete-orphan")


class ReturnRequest(Base):
    __tablename__ = "return_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(ReturnStatus, native_enum=False), default=ReturnStatus.requested, nullable=False)
    reason = Column(Enum(ReturnReason, native_enum=False), nullable=False)
    reason_detail = Column(Text)
    refund_amount = Column(String(20), default="0.00")
    admin_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_return_requests_order_id", "order_id"),
        Index("ix_return_requests_buyer_id", "buyer_id"),
        Index("ix_return_requests_shop_id", "shop_id"),
        Index("ix_return_requests_status", "status"),
    )

    order = relationship("Order", back_populates="return_requests")
    buyer = relationship("User", back_populates="return_requests")
    shop = relationship("Shop", back_populates="return_requests")
    items = relationship("ReturnItem", back_populates="return_request", cascade="all, delete-orphan")


class ReturnItem(Base):
    __tablename__ = "return_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_request_id = Column(UUID(as_uuid=True), ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False)
    order_item_id = Column(UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)
    refund_amount = Column(String(20), default="0.00")
    condition = Column(String(50))  # "new", "used", "damaged"
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    return_request = relationship("ReturnRequest", back_populates="items")
    order_item = relationship("OrderItem", back_populates="return_items")
