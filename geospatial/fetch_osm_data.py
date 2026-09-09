"""
THERMOS — Squad 1 / Person 2
fetch_osm_data.py

Run this for real (needs network access to overpass-api.de — works on a
normal dev machine, not in a locked-down sandbox).

Usage:
    python3 fetch_osm_data.py

Reads DEMO_BBOX from config.py — confirm that value with the team before
running this for the actual demo dataset.
"""

import os
from osm import fetch_industrial_facilities, fetch_landuse_polygons
from config import DEMO_BBOX, bbox_to_overpass

OUTPUT_DIR = os.path.join("..", "data", "processed")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching industrial facilities for bbox {DEMO_BBOX} ...")
    facilities = fetch_industrial_facilities(bbox_to_overpass())
    print(f"  -> {len(facilities)} facilities found")
    if len(facilities) > 0:
        print(facilities["facility_type"].value_counts().to_string())

    print(f"Fetching landuse polygons for bbox {DEMO_BBOX} ...")
    landuse = fetch_landuse_polygons(bbox_to_overpass())
    print(f"  -> {len(landuse)} landuse polygons found")
    if len(landuse) > 0:
        print(landuse["land_cover"].value_counts().to_string())

    facilities_path = os.path.join(OUTPUT_DIR, "industrial_sites.csv")
    facilities.drop(columns="geometry").assign(
        latitude=facilities.geometry.y, longitude=facilities.geometry.x
    ).to_csv(facilities_path, index=False)
    print(f"Saved: {facilities_path}")

    if len(facilities) == 0:
        print("\nWARNING: zero facilities returned. Before assuming Overpass is "
              "broken, check: (1) DEMO_BBOX is actually over land with industry, "
              "(2) OSM_INDUSTRIAL_TAGS in config.py covers the tags used in that "
              "region, (3) Overpass isn't rate-limiting you (wait a bit, retry).")


if __name__ == "__main__":
    main()
