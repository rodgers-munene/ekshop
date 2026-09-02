"""add counties/subcounties/wards reference tables, seed Kenya administrative
data, and add ward_id to user_addresses and shops

Revision ID: f4a29b7c1e05
Revises: d3f8a1c92e47
Create Date: 2026-09-02 00:00:00.000001

"""
import json
import uuid
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f4a29b7c1e05"
down_revision = "d3f8a1c92e47"
branch_labels = None
depends_on = None

DATA_PATH = Path(__file__).resolve().parents[2] / "app" / "data" / "kenya_administrative_units.json"


def upgrade() -> None:
    op.create_table(
        "counties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    op.create_table(
        "subcounties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("county_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("counties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("county_id", "name", name="uq_subcounty_county_name"),
    )
    op.create_index("ix_subcounties_county_id", "subcounties", ["county_id"])
    op.create_table(
        "wards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subcounty_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subcounties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("subcounty_id", "name", name="uq_ward_subcounty_name"),
    )
    op.create_index("ix_wards_subcounty_id", "wards", ["subcounty_id"])

    op.add_column("user_addresses", sa.Column("ward_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wards.id", ondelete="SET NULL"), nullable=True))
    op.add_column("shops", sa.Column("ward_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wards.id", ondelete="SET NULL"), nullable=True))

    _seed()


def _seed() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    counties_table = sa.table("counties", sa.column("id", postgresql.UUID), sa.column("name", sa.String))
    subcounties_table = sa.table(
        "subcounties", sa.column("id", postgresql.UUID), sa.column("county_id", postgresql.UUID), sa.column("name", sa.String)
    )
    wards_table = sa.table(
        "wards", sa.column("id", postgresql.UUID), sa.column("subcounty_id", postgresql.UUID), sa.column("name", sa.String)
    )

    county_rows, subcounty_rows, ward_rows = [], [], []
    for county_name in sorted(data.keys()):
        county_id = uuid.uuid4()
        county_rows.append({"id": county_id, "name": county_name})
        for subcounty_name in sorted(data[county_name].keys()):
            subcounty_id = uuid.uuid4()
            subcounty_rows.append({"id": subcounty_id, "county_id": county_id, "name": subcounty_name})
            for ward_name in data[county_name][subcounty_name]:
                ward_rows.append({"id": uuid.uuid4(), "subcounty_id": subcounty_id, "name": ward_name})

    op.bulk_insert(counties_table, county_rows)
    op.bulk_insert(subcounties_table, subcounty_rows)
    op.bulk_insert(wards_table, ward_rows)


def downgrade() -> None:
    op.drop_column("shops", "ward_id")
    op.drop_column("user_addresses", "ward_id")
    op.drop_index("ix_wards_subcounty_id", table_name="wards")
    op.drop_table("wards")
    op.drop_index("ix_subcounties_county_id", table_name="subcounties")
    op.drop_table("subcounties")
    op.drop_table("counties")
