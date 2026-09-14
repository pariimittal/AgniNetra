import pandas as pd
import sys
import os

# Import the SAME distance constants Squad 1/2 already defined —
# never retype these numbers ourselves.
sys.path.append(os.path.join("..", "geospatial"))
from config import DIST_VERY_CLOSE_M, DIST_NEARBY_M, DIST_REGIONAL_M

def label_row(row):
    industry = row["nearest_industry"]
    land = row["land_cover"]
    dist = row["distance_m"]
    persistence = row["persistence_score"]

    # Industrial Fire: near any industrial facility, some persistence
    if industry in ["refinery", "factory", "power_plant", "industrial_zone"] \
            and dist <= DIST_NEARBY_M and persistence > 0.2:
        return "Industrial Fire"

    # Gas Flare: near oil/gas infra, fairly persistent
    if industry == "oil_gas" and persistence > 0.3:
        return "Gas Flare"

    # Mining Activity: near a mine, any meaningful distance band
    if industry == "mine" and dist <= DIST_REGIONAL_M:
        return "Mining Activity"

    # Wildfire: forest cover, far from any facility
    if land == "forest" and dist > DIST_NEARBY_M:
        return "Wildfire"

    # Agricultural Burning: farmland, short-lived
    if land == "agricultural" and persistence < 0.3:
        return "Agricultural Burning"

    return "Unknown"
def build_training_dataset(
    firms_csv="firms_processed_sample.csv",
    features_csv="anomaly_features.csv",
    out_csv="training_dataset.csv",
):
    firms = pd.read_csv(firms_csv)
    features = pd.read_csv(features_csv)

    if len(firms) == 0:
        raise ValueError(
            f"{firms_csv} has 0 rows — there's nothing to label or train on. This "
            "usually means the upstream FIRMS pull found no detections for the "
            "chosen bbox/day-range. Fix it at the source (firms_pipeline.py): widen "
            "--day-range, try a different --region, or run with --mock to unblock "
            "the demo, then re-run this script."
        )

    merged = firms.merge(features, on=["anomaly_id", "latitude", "longitude"], how="inner")

    if len(merged) == 0:
        raise ValueError(
            f"Merge of {firms_csv} ({len(firms)} rows) and {features_csv} "
            f"({len(features)} rows) produced 0 matching rows on "
            "[anomaly_id, latitude, longitude] — the two files don't share any "
            "anomaly_ids. Check that both were generated from the same FIRMS pull/region."
        )

    merged["classification"] = merged.apply(label_row, axis=1)

    merged.to_csv(out_csv, index=False)
    print(f"Training dataset saved: {out_csv} ({len(merged)} rows)")
    print(merged["classification"].value_counts())
    return merged

if __name__ == "__main__":
    build_training_dataset()