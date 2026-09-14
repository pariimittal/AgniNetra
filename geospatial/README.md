# THERMOS — Squad 1 / Person 2: OSM + Geospatial Features

## What this does
Answers "given this FIRMS point, what's around it?" — produces
`anomaly_features.csv`, Squad 1's contractual output to Squad 2 (AI/ML).

## Files
- `config.py` — distance thresholds, OSM tag taxonomy, output schema, demo bbox. **Change here, not in code.**
- `osm.py` — pulls industrial facilities + landuse polygons from Overpass API for a bbox.
- `features.py` — nearest-facility distance, land-cover lookup, nearest-forest distance,
  population proximity (currently disabled — see decision log below). BallTree +
  haversine, scales to thousands of points without a naive O(n*m) loop.
- `fetch_osm_data.py` — **run this** to pull real OSM data for the team's demo bbox and
  save `industrial_sites.csv`.
- `run_features.py` — **run this** to produce the real `anomaly_features.csv` from a real
  `firms_processed.csv`.
- `test_features.py` — end-to-end test with synthetic FIRMS/OSM-shaped data, no network needed.

## Status as of 2026-09-09 (response to Person 3's review)

| Ask | Status |
|---|---|
| Run the code for real, produce an actual output CSV | **Blocked, not done.** No `firms_processed.csv` (real or sample) exists anywhere in this repo yet — needs Person 1. Overpass API and FIRMS API also aren't reachable from the environment I built this in; both need a normal dev machine with network access. `fetch_osm_data.py` / `run_features.py` are ready to run the moment those two things exist. |
| anomaly_features.csv must match the real firms_processed.csv | Agreed — `run_features.py` reads directly from `../data/processed/firms_processed.csv` and fails loudly (`FileNotFoundError`) if it's missing, rather than silently falling back to any sample file. **Confirm with the team whether the whole demo is running on a sample or on live-pulled data before Day 4** — this determines which file Person 1 hands over. |
| population_proximity decision | **Decided: excluded from output by default.** It's still an unfinished stub with no real data source (WorldPop/GHSL) owned by anyone. Rather than ship a column that's constantly `"unknown"`, `config.INCLUDE_POPULATION_PROXIMITY = False` drops it entirely from `OUTPUT_SCHEMA_COLUMNS` and `compute_features()` skips computing it. Flip that one flag to `True` once someone wires in real population data — no other code changes needed. |
| Bounding box decision | **Still not team-confirmed.** `config.DEMO_BBOX` currently holds a placeholder (Delhi-NCR) with a loud comment. Both `fetch_osm_data.py` and `run_features.py` read from this single constant so the whole team stays in sync once it's picked — don't hardcode a different box in your own script. |

## Getting a real FIRMS MAP_KEY
FIRMS' area CSV endpoint requires a free `MAP_KEY` (not just visiting the map UI) —
register at https://firms.modaps.eosdis.nasa.gov/api/area/ under "Get MAP_KEY".
Whoever on Person 1's side owns the FIRMS pull needs this; it's separate from anything
in this folder.

## Run order (once blockers above are cleared)
```bash
cd geospatial
pip install -r requirements.txt
python3 test_features.py       # sanity check, no network needed — do this first
python3 fetch_osm_data.py      # writes ../data/processed/industrial_sites.csv
python3 run_features.py        # writes ../data/processed/anomaly_features.csv — needs
                                # ../data/processed/firms_processed.csv to already exist
```

## Output schema (anomaly_features.csv)
`anomaly_id, latitude, longitude, nearest_industry, nearest_industry_name, distance_m, land_cover, nearest_forest_km`
(`population_proximity` omitted — see decision log above)
