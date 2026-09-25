import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Text, Table, Boolean, CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ActorRole(str, enum.Enum):
    customer = "customer"
    seller = "seller"
    agent = "agent"
    admin = "admin"


def actor_role_for(role: str) -> ActorRole:
    """Map a UserRole value (or "agent") to the sender role stored on messages;
    buyers are recorded as customers."""
    return ActorRole.customer if role == "buyer" else ActorRole(role)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    shop_id = Column(UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), nullable=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=True)
    last_message_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # One shop chat per buyer and shop, and one chat per order.
    __table_args__ = (
        Index(
            "uq_conversations_buyer_shop", "buyer_id", "shop_id", unique=True,
            postgresql_where=text("order_id IS NULL AND buyer_id IS NOT NULL AND shop_id IS NOT NULL"),
        ),
        Index("uq_conversations_order", "order_id", unique=True, postgresql_where=text("order_id IS NOT NULL")),
    )

    order = relationship("Order")
    buyer = relationship("User", foreign_keys=[buyer_id])
    shop = relationship("Shop", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    participants = relationship("User", secondary="conversation_participants", back_populates="conversations")

    @property
    def shop_name(self):
        return self.shop.name if self.shop else None


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    # Exactly one of these is set: users send as sender_id, delivery agents as sender_agent_id.
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    sender_agent_id = Column(UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="SET NULL"))
    sender_type = Column(Enum(ActorRole, native_enum=False), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")
    sender_agent = relationship("DeliveryAgent")


# Each row is either a user or a delivery agent. Order chats don't use this
# table: their members come from the order (buyer, seller, assigned agent).
conversation_participants = Table(
    "conversation_participants",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")),
    Column("conversation_id", UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    Column("agent_id", UUID(as_uuid=True), ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=True),
    Column("joined_at", DateTime(timezone=True), default=utcnow, nullable=False),
    CheckConstraint("(user_id IS NULL) <> (agent_id IS NULL)", name="ck_conversation_participants_one_actor"),
    Index("uq_conversation_participants_user", "conversation_id", "user_id", unique=True, postgresql_where=text("user_id IS NOT NULL")),
    Index("uq_conversation_participants_agent", "conversation_id", "agent_id", unique=True, postgresql_where=text("agent_id IS NOT NULL")),
)
