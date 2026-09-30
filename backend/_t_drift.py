"""Compare every mapped model's columns against the live database.

Finds model/DB drift: columns a migration never created, and columns the
database has that the model does not know about.
"""
from sqlalchemy import inspect

from app.core.database import engine, Base
import app.models  # noqa: F401  -- ensure every model is imported/mapped

insp = inspect(engine)
db_tables = set(insp.get_table_names())

missing_tables = []
missing_cols = []
extra_cols = []

for table in Base.metadata.sorted_tables:
    name = table.name
    if name not in db_tables:
        missing_tables.append(name)
        continue
    db_cols = {c["name"] for c in insp.get_columns(name)}
    model_cols = {c.name for c in table.columns}
    for col in sorted(model_cols - db_cols):
        missing_cols.append(f"{name}.{col}")
    for col in sorted(db_cols - model_cols):
        extra_cols.append(f"{name}.{col}")

print("=" * 70)
print(f"tables in models but NOT in database ({len(missing_tables)}):")
for t in missing_tables:
    print("   ", t)

print("=" * 70)
print(f"COLUMNS in models but NOT in database ({len(missing_cols)}):")
for c in missing_cols:
    print("   ", c)

print("=" * 70)
print(f"columns in database but not in models ({len(extra_cols)}):")
for c in extra_cols:
    print("   ", c)
