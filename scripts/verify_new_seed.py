"""Verify the new seed CSV has correct geocode_status distribution."""
import pandas as pd

new_path = "src/ca_biositing/pipeline/ca_biositing/pipeline/utils/seed_food_processor_facilities_new.csv"
df = pd.read_csv(new_path, dtype=str)

print(f"New seed CSV rows: {len(df)}")
print()
print("geocode_status breakdown:")
print(df["geocode_status"].value_counts(dropna=False).to_string())
print()

null_lat = df["latitude"].isna().sum()
has_lat = df["latitude"].notna().sum()
print(f"Rows with latitude: {has_lat}")
print(f"Rows without latitude: {null_lat}")
print()

# Check success+null-lat (should be 0 now — DB is clean)
success_mask = df["geocode_status"] == "success"
null_lat_mask = df["latitude"].isna()
bad = (success_mask & null_lat_mask).sum()
print(f"success + null lat (should be 0): {bad}")

# Check duplicates in new CSV
dup_mask = df.duplicated(subset=["name", "address", "city", "zip"], keep=False)
print(f"Rows in duplicate groups (should be 0): {dup_mask.sum()}")

# Check null-zip rows
null_zip = df["zip"].isna().sum()
print(f"Rows with null zip: {null_zip}")

# Check null-zip duplicates using COALESCE logic
df["zip_key"] = df["zip"].fillna("")
coalesce_dups = df.duplicated(subset=["name", "address", "city", "zip_key"], keep=False).sum()
print(f"Rows in COALESCE-key duplicate groups (should be 0): {coalesce_dups}")
