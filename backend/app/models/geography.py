import uuid
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class County(Base):
    __tablename__ = "counties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)

    subcounties = relationship("SubCounty", back_populates="county", cascade="all, delete-orphan")


class SubCounty(Base):
    __tablename__ = "subcounties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    county_id = Column(UUID(as_uuid=True), ForeignKey("counties.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("county_id", "name", name="uq_subcounty_county_name"),
        Index("ix_subcounties_county_id", "county_id"),
    )

    county = relationship("County", back_populates="subcounties")
    wards = relationship("Ward", back_populates="subcounty", cascade="all, delete-orphan")


class Ward(Base):
    __tablename__ = "wards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subcounty_id = Column(UUID(as_uuid=True), ForeignKey("subcounties.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("subcounty_id", "name", name="uq_ward_subcounty_name"),
        Index("ix_wards_subcounty_id", "subcounty_id"),
    )

    subcounty = relationship("SubCounty", back_populates="wards")

    @property
    def subcounty_name(self) -> str:
        return self.subcounty.name

    @property
    def county_name(self) -> str:
        return self.subcounty.county.name
