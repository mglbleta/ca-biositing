"""Diagnostic script for food processing facilities DB state."""
import sys
import pandas as pd
from ca_biositing.pipeline.utils.engine import get_engine
from sqlalchemy import text

engine = get_engine()

with engine.connect() as conn:
    # 1. geocode_status breakdown
    print("=== 1. geocode_status breakdown ===")
    r = conn.execute(text(
        "SELECT geocode_status, COUNT(*) as cnt "
        "FROM infrastructure_food_processing_facilities "
        "GROUP BY geocode_status ORDER BY cnt DESC"
    ))
    for row in r:
        print(f"  geocode_status={row[0]!r}: {row[1]}")

    # 2. Total rows
    print()
    r = conn.execute(text("SELECT COUNT(*) FROM infrastructure_food_processing_facilities"))
    print(f"Total rows: {r.scalar()}")

    # 3. Duplicate conflict keys
    print()
    print("=== 3. Duplicate conflict keys (name, address, city, zip) ===")
    r = conn.execute(text("""
        SELECT name, address, city, zip, COUNT(*) AS copies
        FROM infrastructure_food_processing_facilities
        GROUP BY name, address, city, zip
        HAVING COUNT(*) > 1
        ORDER BY copies DESC
        LIMIT 20
    """))
    rows = r.fetchall()
    print(f"  Duplicate groups: {len(rows)}")
    for row in rows[:10]:
        print(f"  copies={row[4]}: name={row[0]!r}, addr={row[1]!r}, city={row[2]!r}, zip={row[3]!r}")

    # 4. Casing check
    print()
    print("=== 4. Casing consistency ===")
    r = conn.execute(text("""
        SELECT COUNT(*) FROM infrastructure_food_processing_facilities
        WHERE name IS DISTINCT FROM UPPER(name)
           OR address IS DISTINCT FROM UPPER(address)
           OR city IS DISTINCT FROM UPPER(city)
    """))
    print(f"  Rows with non-UPPER casing: {r.scalar()}")

    # 5. Null geocode_status with no lat/lon
    print()
    print("=== 5. Null geocode_status + null lat/lon (first 10) ===")
    r = conn.execute(text("""
        SELECT COUNT(*) FROM infrastructure_food_processing_facilities
        WHERE geocode_status IS NULL AND latitude IS NULL
    """))
    print(f"  Total null-geocode_status + null-lat rows: {r.scalar()}")

    r = conn.execute(text("""
        SELECT processing_facility_id, name, address, city, zip, latitude, longitude, geocode_status
        FROM infrastructure_food_processing_facilities
        WHERE geocode_status IS NULL AND latitude IS NULL
        ORDER BY name
        LIMIT 10
    """))
    for row in r:
        print(f"  id={row[0]}, name={row[1]!r}, city={row[3]!r}, zip={row[4]!r}")

    # 6. Null geocode_status WITH lat/lon (these have coords but no status)
    print()
    print("=== 6. Null geocode_status but HAS lat/lon ===")
    r = conn.execute(text("""
        SELECT COUNT(*) FROM infrastructure_food_processing_facilities
        WHERE geocode_status IS NULL AND latitude IS NOT NULL
    """))
    print(f"  Rows with null geocode_status but have lat/lon: {r.scalar()}")

    # 7. Sample of null geocode_status rows WITH lat/lon
    r = conn.execute(text("""
        SELECT processing_facility_id, name, city, zip, latitude, longitude
        FROM infrastructure_food_processing_facilities
        WHERE geocode_status IS NULL AND latitude IS NOT NULL
        ORDER BY name
        LIMIT 5
    """))
    for row in r:
        print(f"  id={row[0]}, name={row[1]!r}, city={row[2]!r}, lat={row[4]}, lon={row[5]}")

print()
print("=== 8. Seed CSV stats ===")
import os
seed_path = "src/ca_biositing/pipeline/ca_biositing/pipeline/utils/seed_food_processor_facilities.csv"
if os.path.exists(seed_path):
    df = pd.read_csv(seed_path, dtype=str)
    print(f"  Seed CSV rows: {len(df)}")
    print(f"  Seed CSV columns: {list(df.columns)}")
    if "geocode_status" in df.columns:
        print(f"  geocode_status breakdown:")
        print(df["geocode_status"].value_counts(dropna=False).to_string())
    if "latitude" in df.columns:
        null_lat = df["latitude"].isna().sum()
        print(f"  Rows with null latitude: {null_lat}")
else:
    print(f"  Seed CSV not found at {seed_path}")
