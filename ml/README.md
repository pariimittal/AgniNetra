# THERMOS — Squad 2 / Person 3: Classification Model

## ⚠️ Current status (as of tonight, pre-internal-hackathon)
- Pipeline fully working end-to-end on synthetic/mock geospatial data,
  merged with a larger synthetic FIRMS sample (134 rows) for adequate
  training volume. Accuracy: ~89%, Industrial Fire correctly classified
  with ~0.81 confidence.
- Real FIRMS data pull IS working (Person 1's pipeline, region:
  singrauli_coal) — but only returned 4 real detections tonight, too few
  to train on alone.
- Real OSM data (Person 2's anomaly_features.csv) is BLOCKED tonight —
  overpass-api.de and public mirrors down/rate-limited. Tried multiple
  mirrors, retries, longer timeouts, proper headers; confirmed external
  outage via browser + Overpass Turbo, not a code bug.
- **Next step:** retry `python run_features.py` in `geospatial/` before
  the demo, once Overpass access is back. Swap the real `anomaly_features.csv`
  into `ml/`, point `merge_and_label.py` and `mock_features.py` back at
  `data/processed/firms_processed.csv`, rerun the chain. No code changes
  needed beyond the file-path swap already documented in this file.

  
## What this does
Takes anomaly data (Person 1's FIRMS features + Person 2's OSM/geospatial features)
and classifies each thermal anomaly as one of:
Industrial Fire, Gas Flare, Wildfire, Agricultural Burning, Mining Activity, Unknown.

Also outputs a confidence score (0-1) for each prediction.

## Files
- `mock_features.py` — generates a stand-in for Person 2's `anomaly_features.csv`,
  matching real `anomaly_id`s from Person 1's data. **Delete/ignore this once
  Person 2 sends the real file** — just drop their real `anomaly_features.csv`
  into this folder with the same filename and skip this script.
- `merge_and_label.py` — merges Person 1's + Person 2's data on `anomaly_id`,
  then applies rule-based labels (no ground-truth labels exist yet from
  anyone on the team, so this uses distance/persistence thresholds — the
  SAME thresholds Person 2 defined in `geospatial/config.py`, imported
  directly, not retyped).
- `train_model.py` — trains a Random Forest classifier on the labeled data.
  Saves `classification_model.pkl` and `feature_columns.pkl`.
- `model.py` — **this is what Backend (Person 5) imports.** Exposes
  `classify_anomaly(anomaly_dict)` which returns
  `{"classification": ..., "confidence": ...}`.

## How to run (in order)
```bash
cd ml
pip install pandas scikit-learn joblib numpy
python mock_features.py       # skip once real anomaly_features.csv exists
python merge_and_label.py
python train_model.py
python model.py                # sanity check — prints one test prediction
```

## For Backend (Person 5)
```python
from model import classify_anomaly

result = classify_anomaly({
    "brightness": 344.1,
    "confidence": 75.1,
    "detections_30d": 7,
    "persistence_score": 0.54,
    "n_detections_total": 14,
    "distance_m": 420,
    "nearest_forest_km": 8.2,
    "nearest_industry": "refinery",
    "land_cover": "industrial",
    "population_proximity": "high"
})
# result = {"classification": "Industrial Fire", "confidence": 0.85}
```
All 10 fields are required, matching the merged output of Person 1 + Person 2's
schemas (see `geospatial/config.py` and `firms_pipeline.py` for their exact
column definitions).

## Known limitations (current status)
- Dataset is small (134 rows, from `firms_processed_sample.csv` — a *sample*,
  not the full dataset). Classes like Mining Activity and Gas Flare have very
  few examples, so predictions for those are less reliable than Industrial
  Fire / Wildfire / Agricultural Burning.
- `anomaly_features.csv` is currently **mocked** (`mock_features.py`). Swap
  in Person 2's real file (same filename) and rerun the 3 commands above
  once they send it — no code changes needed.
- `population_proximity` is currently always `"unknown"` in Person 2's real
  pipeline (a stub, per their README) — if that doesn't change before the
  demo, it's a low-value feature the model mostly ignores.

## Next steps once real data lands
1. Replace `anomaly_features.csv` with Person 2's real output.
2. Rerun: `merge_and_label.py` → `train_model.py` → `model.py`.
3. Recheck the classification_report printed by `train_model.py` — accuracy
   and per-class scores should improve with more real examples.