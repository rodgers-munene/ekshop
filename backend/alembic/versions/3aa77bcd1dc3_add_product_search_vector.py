"""add product search_vector for full-text search

Revision ID: 3aa77bcd1dc3
Revises: abbafbead62c
Create Date: 2026-07-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision = "3aa77bcd1dc3"
down_revision = "abbafbead62c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column("products", sa.Column("search_vector", TSVECTOR(), nullable=True))

    # array_to_string() is STABLE, not IMMUTABLE, so the vector can't be a
    # GENERATED ALWAYS column -- a BEFORE INSERT/UPDATE trigger keeps it in sync instead
    op.execute(
        """
        CREATE FUNCTION products_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(array_to_string(NEW.tags, ' '), '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER products_search_vector_trigger
        BEFORE INSERT OR UPDATE OF name, description, tags ON products
        FOR EACH ROW EXECUTE FUNCTION products_search_vector_update();
        """
    )

    # backfill existing rows
    op.execute(
        """
        UPDATE products SET search_vector =
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(array_to_string(tags, ' '), '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'C');
        """
    )

    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_products_name_trgm",
        "products",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_products_name_trgm", table_name="products")
    op.drop_index("ix_products_search_vector", table_name="products")
    op.execute("DROP TRIGGER IF EXISTS products_search_vector_trigger ON products")
    op.execute("DROP FUNCTION IF EXISTS products_search_vector_update()")
    op.drop_column("products", "search_vector")
