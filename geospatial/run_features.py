"""
THERMOS — Squad 1 / Person 2
run_features.py

Produces the real anomaly_features.csv handed to Squad 2 (AI/ML).

Requires:
  - ../data/processed/firms_processed.csv  (from Person 1 — same run/date
    range the whole team is using for the demo, not an arbitrary sample)
  - network access to overpass-api.de (re-fetches OSM data live; swap to
    read from ../data/processed/industrial_sites.csv if you want to reuse
    a previous fetch_osm_data.py run instead of hitting Overpass twice)

Usage:
    python3 run_features.py
"""

import os
import pandas as pd

from osm import fetch_industrial_facilities, fetch_landuse_polygons
from features import compute_features
from config import DEMO_BBOX, bbox_to_overpass

FIRMS_INPUT_PATH = os.path.join("..", "data", "processed", "firms_processed.csv")
OUTPUT_PATH = os.path.join("..", "data", "processed", "anomaly_features.csv")


def main():
    if not os.path.exists(FIRMS_INPUT_PATH):
        raise FileNotFoundError(
            f"{FIRMS_INPUT_PATH} not found. This must be the real "
            f"firms_processed.csv from Person 1 — same data run the whole "
            f"team is using for the demo. Ask Person 1 for it before running this."
        )

    firms_df = pd.read_csv(FIRMS_INPUT_PATH)
    required = {"anomaly_id", "latitude", "longitude"}
    missing = required - set(firms_df.columns)
    if missing:
        raise ValueError(
            f"firms_processed.csv is missing required columns {missing}. "
            f"Check with Person 1 — column names must match the frozen schema exactly."
        )

    print(f"Loaded {len(firms_df)} FIRMS points from {FIRMS_INPUT_PATH}")

    print(f"Fetching OSM data for bbox {DEMO_BBOX} ...")
    facilities = fetch_industrial_facilities(bbox_to_overpass())
    landuse = fetch_landuse_polygons(bbox_to_overpass())
    print(f"  -> {len(facilities)} facilities, {len(landuse)} landuse polygons")

    result = compute_features(firms_df, facilities, landuse, population_df=None)

    result.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved: {OUTPUT_PATH} ({len(result)} rows)")
    print(result.head())


if __name__ == "__main__":
    main()
