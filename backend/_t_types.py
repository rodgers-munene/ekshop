"""Check the real types of the money/int columns we must match."""
from sqlalchemy import inspect

from app.core.database import engine

insp = inspect(engine)
for t, cols in [
    ("orders", ["subtotal", "delivery_fee", "total"]),
    ("order_groups", ["subtotal", "delivery_fee", "total"]),
    ("order_items", ["price", "quantity"]),
    ("products", ["stock"]),
    ("product_variants", ["stock"]),
    ("shops", ["name"]),
    ("user_addresses", ["county"]),
    ("messages", ["is_read"]),
]:
    for c in insp.get_columns(t):
        if c["name"] in cols:
            print(f"  {t}.{c['name']:<14} {str(c['type']):<18} nullable={c['nullable']} default={c.get('default')}")
