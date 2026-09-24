"""stage bulk product imports so a spreadsheet can be reviewed before it lands

A seller's stock export is thousands of rows -- the sample this was built
against is 9,608 -- which is too much for one request and too much to trust
sight unseen. So an upload is parsed into product_import_rows first, the seller
reviews the counts, and only then are products created, in batches, as drafts.

Rows keep their own status, so a commit interrupted half way through resumes
instead of double-creating.

Revision ID: c9e2a4f17b53
Revises: a3f81c26d945
Create Date: 2026-09-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c9e2a4f17b53"
down_revision = "a3f81c26d945"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_imports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "parsing", "ready", "processing", "completed", "failed", "cancelled",
                name="importstatus", native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column(
            "on_duplicate",
            sa.Enum(
                "skip", "update_stock_price", "create_new",
                name="duplicateaction", native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("matched_rows", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_imports_shop_id", "product_imports", ["shop_id"])

    op.create_table(
        "product_import_rows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("import_id", sa.UUID(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("price", sa.String(length=20), nullable=True),
        sa.Column("stock_qty", sa.Integer(), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("matched_product_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "valid", "invalid", "created", "updated", "skipped", "failed",
                name="importrowstatus", native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["import_id"], ["product_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_import_rows_import_status",
        "product_import_rows",
        ["import_id", "status"],
    )

    # Makes (shop_id, sku) -- the importer's dedupe key -- an indexed lookup
    # instead of a scan per batch. Deliberately NOT unique: sku has always been
    # free-form, so shops may already hold duplicates, and adding uniqueness
    # here would both risk failing this migration on live data and start
    # rejecting product creates that work today. The importer resolves a
    # duplicate by taking the oldest match, which is stable without a
    # constraint. Tighten to unique in its own migration once the data is known
    # clean.
    op.create_index(
        "ix_products_shop_sku",
        "products",
        ["shop_id", "sku"],
        postgresql_where=sa.text("sku IS NOT NULL AND sku <> ''"),
    )


def downgrade() -> None:
    op.drop_index("ix_products_shop_sku", table_name="products")
    op.drop_index("ix_product_import_rows_import_status", table_name="product_import_rows")
    op.drop_table("product_import_rows")
    op.drop_index("ix_product_imports_shop_id", table_name="product_imports")
    op.drop_table("product_imports")
