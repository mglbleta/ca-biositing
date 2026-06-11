"""
Compare DB state vs seed CSV to understand the discrepancy.

DB: 146 success (all with lat/lon), 188 failed, 5822 NULL = 6156 total
Seed CSV: 5920 success (5789 null-lat, 131 with lat), 188 failed, 48 NaN = 6156 total

Key question: how did the seed CSV get 5920 success rows when the DB only has 146?
"""
import pandas as pd
from ca_biositing.pipeline.utils.engine import get_engine
from sqlalchemy import text

engine = get_engine()
seed_path = "src/ca_biositing/pipeline/ca_biositing/pipeline/utils/seed_food_processor_facilities.csv"
df_seed = pd.read_csv(seed_path, dtype=str)

print("=== DB vs Seed CSV comparison ===")
print(f"Seed CSV rows: {len(df_seed)}")

with engine.connect() as conn:
    r = conn.execute(text("SELECT COUNT(*) FROM infrastructure_food_processing_facilities"))
    print(f"DB rows: {r.scalar()}")

    # Check: are the 5789 success+null-lat rows in the seed CSV present in the DB?
    # If they are, they should have geocode_status=NULL in the DB (since _clean_seed_df step 7b resets them)
    # Let's pick a few and check their DB state
    r = conn.execute(text("""
        SELECT name, address, city, zip, latitude, longitude, geocode_status
        FROM infrastructure_food_processing_facilities
        WHERE name = '4 CORNER GROWERS LLC'
    """))
    rows = r.fetchall()
    print(f"\n'4 CORNER GROWERS LLC' in DB ({len(rows)} rows):")
    for row in rows:
        print(f"  name={row[0]!r}, addr={row[1]!r}, city={row[2]!r}, zip={row[3]!r}, lat={row[4]}, geocode_status={row[6]!r}")

    r = conn.execute(text("""
        SELECT name, address, city, zip, latitude, longitude, geocode_status
        FROM infrastructure_food_processing_facilities
        WHERE name = 'ADRIAN RANCH'
    """))
    rows = r.fetchall()
    print(f"\n'ADRIAN RANCH' in DB ({len(rows)} rows):")
    for row in rows:
        print(f"  name={row[0]!r}, addr={row[1]!r}, city={row[2]!r}, zip={row[3]!r}, lat={row[4]}, geocode_status={row[6]!r}")

    # The CIRCUIT BREAKER: GEOCODE_ROW_LIMIT = 50
    # When GEOCODE_TARGET='all_facilities' ran, how many rows were queued?
    # The delta check skips rows already in DB with lat/lon OR geocode_status='failed'
    # At the time of the run, the DB had 0 rows (fresh), so ALL ~6000 rows were queued
    # But GEOCODE_ROW_LIMIT = 50 would have fired!
    # UNLESS the circuit breaker was raised or removed for that run.
    # Let's check: the seed CSV has 5920 success rows — that's way more than 50.
    # So either the circuit breaker was bypassed, or the geocoder ran in batches.

    print("\n=== Hypothesis: geocoder ran with circuit breaker bypassed ===")
    print("Seed CSV success rows: 5920 (way more than GEOCODE_ROW_LIMIT=50)")
    print("This means the circuit breaker was either raised or the geocoder ran multiple times")
    print()

    # Check: what's the geocode_status distribution for rows WITH zip vs WITHOUT zip in DB?
    r = conn.execute(text("""
        SELECT
            CASE WHEN zip IS NULL THEN 'null_zip' ELSE 'has_zip' END as zip_status,
            geocode_status,
            COUNT(*)
        FROM infrastructure_food_processing_facilities
        GROUP BY zip IS NULL, geocode_status
        ORDER BY zip IS NULL, geocode_status
    """))
    print("DB geocode_status by zip presence:")
    for row in r:
        print(f"  {row[0]}, geocode_status={row[1]!r}: {row[2]}")

print()
print("=== Seed CSV: success+null-lat rows — do they have valid addresses? ===")
success_null_lat = df_seed[(df_seed["geocode_status"] == "success") & (df_seed["latitude"].isna())]
print(f"Count: {len(success_null_lat)}")
print(f"With address: {success_null_lat['address'].notna().sum()}")
print(f"With zip: {success_null_lat['zip'].notna().sum()}")
print()
print("Sample (first 5):")
print(success_null_lat[["name", "address", "city", "zip", "latitude", "geocode_status"]].head(5).to_string())

print()
print("=== CONCLUSION ===")
print("The seed CSV was exported from a DB state where geocode_status='success' was set")
print("for ~5920 rows but lat/lon was NULL. This is the 'geocode_status written without lat/lon' bug.")
print("The current DB (146 success rows all with lat/lon) is the CORRECT state after _clean_seed_df")
print("step 7b reset the bad success rows back to NULL.")
print()
print("The geocoder must have set geocode_status='success' without storing lat/lon.")
print("This could happen if the UPSERT update_dict included geocode_status but NOT latitude/longitude,")
print("OR if the geocoder returned success but lat/lon was NaN (not None) and the fillna() missed it.")
