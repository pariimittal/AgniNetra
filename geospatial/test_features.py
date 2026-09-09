"""
Quick end-to-end sanity test using synthetic data shaped like real
FIRMS output (Person 1) and real OSM output (osm.py in this module).

Run: python3 test_features.py

This does NOT hit the network (Overpass isn't reachable from this sandbox)
— it mocks fetch_industrial_facilities()/fetch_landuse_polygons() output
directly so Squad 2 can start integrating against the real schema today,
per the Day 1-3 "use mock data, don't wait" plan.
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from features import compute_features

# ---------------------------------------------------------------------------
# Synthetic FIRMS points (Delhi-NCR area, mimicking Person 1's output)
# ---------------------------------------------------------------------------
firms_df = pd.DataFrame([
    # Right on top of a refinery -> should classify as close/industrial
    {"anomaly_id": "ANM001", "latitude": 28.4700, "longitude": 77.3200},
    # Deep in a forest polygon, far from any facility -> wildfire-ish signal
    {"anomaly_id": "ANM002", "latitude": 28.6000, "longitude": 77.6500},
    # In farmland, moderate distance from facility -> agri-burning-ish signal
    {"anomaly_id": "ANM003", "latitude": 28.5200, "longitude": 77.1000},
    # Isolated point, no facility/landuse polygon covers it -> unknown/other
    {"anomaly_id": "ANM004", "latitude": 29.1000, "longitude": 76.9000},
])

# ---------------------------------------------------------------------------
# Synthetic OSM industrial facilities (shape matches osm.py output exactly)
# ---------------------------------------------------------------------------
facilities_gdf = gpd.GeoDataFrame([
    {"osm_id": "way/1", "name": "NCR Refinery", "facility_type": "refinery",
     "raw_tags": {}, "geometry": Point(77.3210, 28.4695)},
    {"osm_id": "node/2", "name": "Delhi Thermal Power Plant", "facility_type": "power_plant",
     "raw_tags": {}, "geometry": Point(77.1500, 28.5300)},
    {"osm_id": "way/3", "name": "Faridabad Steel Works", "facility_type": "factory",
     "raw_tags": {}, "geometry": Point(77.3000, 28.4000)},
], geometry="geometry", crs="EPSG:4326")

# ---------------------------------------------------------------------------
# Synthetic landuse polygons (shape matches osm.py output exactly)
# ---------------------------------------------------------------------------
landuse_gdf = gpd.GeoDataFrame([
    {"osm_id": "way/10", "land_cover": "forest",
     "geometry": Polygon([(77.63, 28.58), (77.68, 28.58), (77.68, 28.62), (77.63, 28.62)])},
    {"osm_id": "way/11", "land_cover": "agricultural",
     "geometry": Polygon([(77.08, 28.50), (77.12, 28.50), (77.12, 28.54), (77.08, 28.54)])},
], geometry="geometry", crs="EPSG:4326")

if __name__ == "__main__":
    result = compute_features(firms_df, facilities_gdf, landuse_gdf, population_df=None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
    print(result)
    print()
    from config import OUTPUT_SCHEMA_COLUMNS
    assert list(result.columns) == OUTPUT_SCHEMA_COLUMNS, (
        f"Output columns {list(result.columns)} don't match "
        f"config.OUTPUT_SCHEMA_COLUMNS {OUTPUT_SCHEMA_COLUMNS}"
    )
    print("Schema check passed. Output columns match config.OUTPUT_SCHEMA_COLUMNS.")
    print(f"(population_proximity included: {('population_proximity' in result.columns)})")
