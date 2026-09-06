# THERMOS — Squad 1 / Person 2: OSM + Geospatial Features

## What this does
Answers "given this FIRMS point, what's around it?" — produces
`anomaly_features.csv`, Squad 1's contractual output to Squad 2 (AI/ML).

## Files
- `config.py` — distance thresholds, OSM tag taxonomy, output schema. **Change here, not in code.**
- `osm.py` — pulls industrial facilities + landuse polygons from Overpass API for a bbox.
- `features.py` — nearest-facility distance, land-cover lookup, nearest-forest distance,
  population proximity (stub — see below). Uses a BallTree with haversine metric so it
  scales to thousands of FIRMS points without a naive O(n*m) loop.
- `test_features.py` — end-to-end test with synthetic FIRMS/OSM-shaped data, no network needed.
  Run this first to confirm the pipeline + schema before wiring in real data.

## Decisions made (flag if team disagrees)
1. **Land cover = OSM landuse/natural polygons**, not a raster product (ESA WorldCover etc).
   Faster, no GDAL dependency, but coverage will be patchy in some areas — `"unknown"` is an
   expected, valid output, not a bug.
2. **Distance thresholds live in `config.py`** (`DIST_VERY_CLOSE_M=500`, `DIST_NEARBY_M=2000`,
   `DIST_REGIONAL_M=10000`). Squad 2's risk engine should read these same constants rather
   than hardcoding its own numbers.
3. **Population proximity is currently a stub** returning `"unknown"` — nobody owns sourcing
   real population data (WorldPop/GHSL) in the current squad plan. `population_proximity()`
   is already wired to accept a `population_df` and will just work once that's plugged in —
   whoever picks this up doesn't need to touch `features.py`.

## Next steps for real data
1. Pick the demo bounding box (south, west, north, east) as a team — don't query all of OSM.
2. Run `osm.fetch_industrial_facilities(bbox)` and `osm.fetch_landuse_polygons(bbox)` for real
   (needs network access to overpass-api.de — not available in this sandbox, works in normal dev env).
3. Feed Person 1's cleaned FIRMS dataframe into `features.compute_features(...)`.
4. Write result to `/data/anomaly_features.csv` per the frozen schema.

## Output schema (anomaly_features.csv)
anomaly_id, latitude, longitude, nearest_industry, nearest_industry_name,
distance_m, land_cover, nearest_forest_km, population_proximity
