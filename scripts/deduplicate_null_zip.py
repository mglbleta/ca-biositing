"""
Deduplicate null-zip rows in infrastructure_food_processing_facilities.

The old UNIQUE (name, address, city, zip) constraint treated NULL != NULL,
so each ETL run INSERTed a new row for facilities without a ZIP code.
This script keeps the best row per (name, address, city) group where zip IS NULL:
  - prefer the row with lat/lon (geocode_status='success')
  - among ties, keep the row with the highest processing_facility_id (most recent)

Run this BEFORE applying migration 0015 (which creates the new functional index).
The new index will fail to create if duplicates still exist.
"""
from ca_biositing.pipeline.utils.engine import get_engine
from sqlalchemy import text

engine = get_engine()

with engine.connect() as conn:
    with conn.begin():
        # 1. Show current state
        r = conn.execute(text(
            "SELECT COUNT(*) FROM infrastructure_food_processing_facilities WHERE zip IS NULL"
        ))
        print(f"Rows with null zip before dedup: {r.scalar()}")

        r = conn.execute(text("SELECT COUNT(*) FROM infrastructure_food_processing_facilities"))
        print(f"Total rows before dedup: {r.scalar()}")

        # 2. Find duplicate groups (null-zip rows with same name/address/city)
        r = conn.execute(text("""
            SELECT name, address, city, COUNT(*) as copies
            FROM infrastructure_food_processing_facilities
            WHERE zip IS NULL
            GROUP BY name, address, city
            HAVING COUNT(*) > 1
            ORDER BY copies DESC
        """))
        dup_groups = r.fetchall()
        print(f"\nDuplicate null-zip groups: {len(dup_groups)}")
        for row in dup_groups[:10]:
            print(f"  copies={row[3]}: name={row[0]!r}, addr={row[1]!r}, city={row[2]!r}")

        # 3. Delete duplicates: keep the best row per group.
        #    "Best" = has lat/lon (geocode_status='success'), then highest ID.
        #    We use a CTE to rank rows within each duplicate group and delete
        #    all but the top-ranked row.
        result = conn.execute(text("""
            WITH ranked AS (
                SELECT
                    processing_facility_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY name, address, city
                        ORDER BY
                            -- prefer rows with lat/lon
                            CASE WHEN latitude IS NOT NULL THEN 0 ELSE 1 END,
                            -- then prefer rows with geocode_status='success'
                            CASE WHEN geocode_status = 'success' THEN 0 ELSE 1 END,
                            -- then keep the most recent (highest ID)
                            processing_facility_id DESC
                    ) AS rn
                FROM infrastructure_food_processing_facilities
                WHERE zip IS NULL
            )
            DELETE FROM infrastructure_food_processing_facilities
            WHERE processing_facility_id IN (
                SELECT processing_facility_id FROM ranked WHERE rn > 1
            )
            RETURNING processing_facility_id
        """))
        deleted_ids = result.fetchall()
        print(f"\nDeleted {len(deleted_ids)} duplicate null-zip rows")

        # 4. Verify
        r = conn.execute(text(
            "SELECT COUNT(*) FROM infrastructure_food_processing_facilities WHERE zip IS NULL"
        ))
        print(f"Rows with null zip after dedup: {r.scalar()}")

        r = conn.execute(text("SELECT COUNT(*) FROM infrastructure_food_processing_facilities"))
        print(f"Total rows after dedup: {r.scalar()}")

        # 5. Confirm no more duplicates
        r = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT name, address, city
                FROM infrastructure_food_processing_facilities
                WHERE zip IS NULL
                GROUP BY name, address, city
                HAVING COUNT(*) > 1
            ) dups
        """))
        remaining_dups = r.scalar()
        print(f"Remaining duplicate null-zip groups: {remaining_dups}")

        if remaining_dups > 0:
            print("WARNING: Still have duplicates — migration 0015 will fail!")
        else:
            print("OK: No more null-zip duplicates. Safe to run migration 0015.")

        # 6. Also check for duplicates among has-zip rows (shouldn't exist but verify)
        r = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT name, address, city, zip
                FROM infrastructure_food_processing_facilities
                WHERE zip IS NOT NULL
                GROUP BY name, address, city, zip
                HAVING COUNT(*) > 1
            ) dups
        """))
        has_zip_dups = r.scalar()
        print(f"Duplicate has-zip groups: {has_zip_dups}")
        if has_zip_dups > 0:
            print("WARNING: Has-zip duplicates exist — these will also block migration 0015!")
