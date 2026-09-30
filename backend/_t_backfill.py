"""Inspect existing rows that need backfilling before adding NOT NULL columns."""
import uuid

from sqlalchemy import text

from app.core.database import SessionLocal

s = SessionLocal()

print("messages total / with sender:", s.execute(text(
    "SELECT count(*) FILTER (WHERE sender_id IS NOT NULL), count(*) FROM messages")).first())
print("\nmessages by sender role:")
for role, n in s.execute(text(
        "SELECT coalesce(u.role::text, '<null sender>'), count(*) FROM messages m "
        "LEFT JOIN users u ON u.id = m.sender_id GROUP BY 1 ORDER BY 2 DESC")):
    print(f"   {role:<20} {n}")
print("\nusers.role distribution:")
for role, n in s.execute(text("SELECT role::text, count(*) FROM users GROUP BY 1 ORDER BY 2 DESC")):
    print(f"   {role:<20} {n}")

print("\nrow counts for tables gaining NOT NULL columns:")
for t, cols in [
    ("orders", ["total", "subtotal"]),
    ("order_groups", ["total"]),
    ("order_items", ["price", "quantity"]),
    ("products", ["stock"]),
    ("product_variants", ["stock"]),
    ("shops", ["name"]),
    ("user_addresses", ["county"]),
]:
    n = s.execute(text(f"SELECT count(*) FROM {t}")).scalar()
    print(f"   {t:<20} {n} rows")

s.close()
