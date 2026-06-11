"""Check indexes and constraints on the food processing facilities table."""
from ca_biositing.pipeline.utils.engine import get_engine
from sqlalchemy import text

engine = get_engine()

with engine.connect() as conn:
    r = conn.execute(text("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'infrastructure_food_processing_facilities'
        ORDER BY indexname
    """))
    rows = r.fetchall()
    print(f"Indexes ({len(rows)}):")
    for row in rows:
        print(f"  {row[0]}")
        print(f"    {row[1]}")

    print()
    r = conn.execute(text("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'infrastructure_food_processing_facilities'::regclass
        ORDER BY conname
    """))
    rows = r.fetchall()
    print(f"Constraints ({len(rows)}):")
    for row in rows:
        print(f"  {row[0]} (type={row[1]}): {row[2]}")

    print()
    # Check the SQLModel model's unique constraint definition
    print("=== Checking model definition ===")

print()
from ca_biositing.datamodels.models import InfrastructureFoodProcessingFacilities
t = InfrastructureFoodProcessingFacilities.__table__
print(f"Table: {t.name}")
print(f"Columns: {[c.name for c in t.columns]}")
print(f"Constraints:")
for c in t.constraints:
    print(f"  {c}")
print(f"Indexes:")
for idx in t.indexes:
    print(f"  {idx.name}: {[c.name for c in idx.columns]} unique={idx.unique}")
