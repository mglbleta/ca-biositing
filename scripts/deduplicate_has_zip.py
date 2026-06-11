"""
Find and deduplicate has-zip duplicate rows in infrastructure_food_processing_facilities.

These are rows where zip IS NOT NULL but (name, address, city, zip) is duplicated.
This should not happen with the old unique constraint, but may have occurred if
the constraint was added after data was already loaded.
"""
from ca_biositing.pipeline.utils.engine import get_engine
from sqlalchemy import text

engine = get_engine()

with engine.connect() as conn:
    # Show the duplicate has-zip groups
    r = conn.execute(text("""
        SELECT name, address, city, zip, COUNT(*) as copies,
               array_agg(processing_facility_id ORDER BY processing_facility_id) as ids
        FROM infrastructure_food_processing_facilities
        WHERE zip IS NOT NULL
        GROUP BY name, address, city, zip
        HAVING COUNT(*) > 1
        ORDER BY copies DESC
    """))
    rows = r.fetchall()
    print(f"Has-zip duplicate groups: {len(rows)}")
    for row in rows:
        print(f"  copies={row[4]}: name={row[0]!r}, addr={row[1]!r}, city={row[2]!r}, zip={row[3]!r}")
        print(f"    IDs: {row[5]}")

    print()
    # Show full details for each duplicate group
    for row in rows:
        name, addr, city, zip_val = row[0], row[1], row[2], row[3]
        r2 = conn.execute(text("""
            SELECT processing_facility_id, name, address, city, zip,
                   latitude, longitude, geocode_status, created_at
            FROM infrastructure_food_processing_facilities
            WHERE name = :name AND address = :addr AND city = :city AND zip = :zip
            ORDER BY processing_facility_id
        """), {"name": name, "addr": addr, "city": city, "zip": zip_val})
        detail_rows = r2.fetchall()
        print(f"Group: {name!r} / {addr!r} / {city!r} / {zip_val!r}")
        for dr in detail_rows:
            print(f"  id={dr[0]}, lat={dr[5]}, geocode_status={dr[7]!r}, created={dr[8]}")

with engine.connect() as conn:
    with conn.begin():
        # Delete duplicates: keep best row (lat/lon preferred, then highest ID)
        result = conn.execute(text("""
            WITH ranked AS (
                SELECT
                    processing_facility_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY name, address, city, zip
                        ORDER BY
                            CASE WHEN latitude IS NOT NULL THEN 0 ELSE 1 END,
                            CASE WHEN geocode_status = 'success' THEN 0 ELSE 1 END,
                            processing_facility_id DESC
                    ) AS rn
                FROM infrastructure_food_processing_facilities
                WHERE zip IS NOT NULL
            )
            DELETE FROM infrastructure_food_processing_facilities
            WHERE processing_facility_id IN (
                SELECT processing_facility_id FROM ranked WHERE rn > 1
            )
            RETURNING processing_facility_id
        """))
        deleted = result.fetchall()
        print(f"\nDeleted {len(deleted)} has-zip duplicate rows: {[r[0] for r in deleted]}")

        r = conn.execute(text("SELECT COUNT(*) FROM infrastructure_food_processing_facilities"))
        print(f"Total rows after dedup: {r.scalar()}")

        # Final check: any duplicates remaining?
        r = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT name, address, city, COALESCE(zip, '') as zip_key
                FROM infrastructure_food_processing_facilities
                GROUP BY name, address, city, COALESCE(zip, '')
                HAVING COUNT(*) > 1
            ) dups
        """))
        remaining = r.scalar()
        print(f"Remaining duplicates (COALESCE key): {remaining}")
        if remaining == 0:
            print("OK: No duplicates remain. Safe to run migration 0015.")
        else:
            print("WARNING: Still have duplicates!")
