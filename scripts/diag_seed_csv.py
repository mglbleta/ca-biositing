"""Diagnose the seed CSV geocode_status vs latitude mismatch."""
import pandas as pd

seed_path = "src/ca_biositing/pipeline/ca_biositing/pipeline/utils/seed_food_processor_facilities.csv"
df = pd.read_csv(seed_path, dtype=str)

print(f"Seed CSV rows: {len(df)}")
print()

# Check geocode_status='success' rows with null latitude
success_mask = df["geocode_status"] == "success"
null_lat_mask = df["latitude"].isna() | (df["latitude"].str.strip() == "")

print(f"geocode_status='success': {success_mask.sum()}")
print(f"latitude is null/blank: {null_lat_mask.sum()}")
print(f"geocode_status='success' AND latitude is null: {(success_mask & null_lat_mask).sum()}")
print(f"geocode_status='success' AND latitude is NOT null: {(success_mask & ~null_lat_mask).sum()}")
print()

# Show some success rows with null lat
print("=== Sample 'success' rows with null latitude ===")
bad = df[success_mask & null_lat_mask][["name", "city", "zip", "latitude", "longitude", "geocode_status"]].head(10)
print(bad.to_string())
print()

# Show some success rows WITH lat
print("=== Sample 'success' rows WITH latitude ===")
good = df[success_mask & ~null_lat_mask][["name", "city", "zip", "latitude", "longitude", "geocode_status"]].head(10)
print(good.to_string())
print()

# Check the 48 NaN geocode_status rows
nan_mask = df["geocode_status"].isna()
print(f"=== 48 NaN geocode_status rows ===")
print(f"Count: {nan_mask.sum()}")
nan_rows = df[nan_mask][["name", "city", "zip", "latitude", "longitude", "geocode_status"]].head(10)
print(nan_rows.to_string())
print()

# Check duplicate conflict keys in seed CSV
print("=== Duplicate conflict keys in seed CSV ===")
dup_mask = df.duplicated(subset=["name", "address", "city", "zip"], keep=False)
print(f"Rows involved in duplicates: {dup_mask.sum()}")
dups = df[dup_mask].groupby(["name", "address", "city", "zip"]).size().reset_index(name="copies")
dups = dups.sort_values("copies", ascending=False)
print(dups.head(10).to_string())
print()

# Check zip=None duplicates specifically
print("=== Rows with null zip ===")
null_zip = df["zip"].isna() | (df["zip"].str.strip() == "") | (df["zip"] == "nan")
print(f"Rows with null/blank zip: {null_zip.sum()}")
print(df[null_zip][["name", "address", "city", "zip", "geocode_status", "latitude"]].head(10).to_string())
