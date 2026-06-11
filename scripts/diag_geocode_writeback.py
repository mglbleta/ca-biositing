"""
Diagnose the geocoder lat/lon write-back bug.

The seed CSV has 5789 rows with geocode_status='success' but null latitude.
This means the geocoder ran and set geocode_status='success' but lat/lon
was not stored in the DB. We need to understand why.

Key question: does the DB have ANY rows with geocode_status='success' and lat/lon?
If yes, the write-back works for some rows but not others.
If no, the write-back is completely broken.
"""
import pandas as pd
from ca_biositing.pipeline.utils.engine import get_engine
from sqlalchemy import text

engine = get_engine()

with engine.connect() as conn:
    # How many success rows have lat/lon in DB?
    r = conn.execute(text(
        "SELECT COUNT(*) FROM infrastructure_food_processing_facilities "
        "WHERE geocode_status = 'success' AND latitude IS NOT NULL"
    ))
    print(f"success + lat NOT NULL: {r.scalar()}")

    r = conn.execute(text(
        "SELECT COUNT(*) FROM infrastructure_food_processing_facilities "
        "WHERE geocode_status = 'success' AND latitude IS NULL"
    ))
    print(f"success + lat IS NULL: {r.scalar()}")

    # Show sample success rows WITH lat
    r = conn.execute(text(
        "SELECT name, city, zip, latitude, longitude, geocode_status "
        "FROM infrastructure_food_processing_facilities "
        "WHERE geocode_status = 'success' AND latitude IS NOT NULL "
        "LIMIT 5"
    ))
    rows = r.fetchall()
    print(f"\nSample success+lat rows ({len(rows)}):")
    for row in rows:
        print(f"  name={row[0]!r}, city={row[1]!r}, zip={row[2]!r}, lat={row[3]}, lon={row[4]}")

    # Show sample success rows WITHOUT lat
    r = conn.execute(text(
        "SELECT name, city, zip, latitude, longitude, geocode_status "
        "FROM infrastructure_food_processing_facilities "
        "WHERE geocode_status = 'success' AND latitude IS NULL "
        "LIMIT 5"
    ))
    rows = r.fetchall()
    print(f"\nSample success+null-lat rows ({len(rows)}):")
    for row in rows:
        print(f"  name={row[0]!r}, city={row[1]!r}, zip={row[2]!r}, lat={row[3]}, lon={row[4]}")

    # What's the zip distribution for success rows?
    r = conn.execute(text(
        "SELECT zip IS NULL as zip_null, COUNT(*) "
        "FROM infrastructure_food_processing_facilities "
        "WHERE geocode_status = 'success' "
        "GROUP BY zip IS NULL"
    ))
    print("\nSuccess rows by zip_null:")
    for row in r:
        print(f"  zip_null={row[0]}: {row[1]}")

    # Check: are the 146 success rows in DB the same as the 131 success+lat rows in seed CSV?
    # The seed CSV had 131 success+lat rows. DB has 146 success rows.
    # Let's see what zip the 146 success rows have
    r = conn.execute(text(
        "SELECT zip, COUNT(*) FROM infrastructure_food_processing_facilities "
        "WHERE geocode_status = 'success' "
        "GROUP BY zip ORDER BY COUNT(*) DESC LIMIT 10"
    ))
    print("\nSuccess rows by zip (top 10):")
    for row in r:
        print(f"  zip={row[0]!r}: {row[1]}")

print()
print("=== Seed CSV analysis ===")
seed_path = "src/ca_biositing/pipeline/ca_biositing/pipeline/utils/seed_food_processor_facilities.csv"
df = pd.read_csv(seed_path, dtype=str)

# The 131 success+lat rows in seed CSV — what are their zips?
success_mask = df["geocode_status"] == "success"
null_lat_mask = df["latitude"].isna() | (df["latitude"].str.strip() == "")
has_lat_mask = ~null_lat_mask

print(f"Seed CSV success+lat rows: {(success_mask & has_lat_mask).sum()}")
print(f"Seed CSV success+null-lat rows: {(success_mask & null_lat_mask).sum()}")

# Show zip distribution for success+lat rows
good = df[success_mask & has_lat_mask]
print(f"\nZip distribution for success+lat rows:")
print(good["zip"].value_counts(dropna=False).head(10).to_string())

# The 5789 success+null-lat rows — what's special about them?
bad = df[success_mask & null_lat_mask]
print(f"\nZip distribution for success+null-lat rows (top 10):")
print(bad["zip"].value_counts(dropna=False).head(10).to_string())

# Check: do the success+null-lat rows have addresses?
print(f"\nSuccess+null-lat rows with null address: {bad['address'].isna().sum()}")
print(f"Success+null-lat rows with address: {bad['address'].notna().sum()}")
print(f"\nSample success+null-lat rows with address:")
print(bad[bad["address"].notna()][["name", "address", "city", "zip", "latitude", "geocode_status"]].head(5).to_string())
