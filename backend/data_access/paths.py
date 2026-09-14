"""
backend/data_access/paths.py

Absolute, cwd-independent paths to the repository's data files and
component directories. Every path is derived from `backend.config.REPO_ROOT`
(itself computed from this file's own location), never from the process's
current working directory — this is what lets the backend run correctly via
`uvicorn backend.main:app --reload` from the repository root, regardless of
where the *caller* happens to have their shell cwd.

This module does NOT read any files — it only resolves paths. Actual
loading (with fallback / missing-data handling) lives in
`backend/data_access/anomaly_source.py`.
"""

from __future__ import annotations

import os

from backend._repo_root import REPO_ROOT

# --- Component directories (owned by Persons 1-4, per Phase 1 audit) ------
ML_DIR = os.path.join(REPO_ROOT, "ml")
GEOSPATIAL_DIR = os.path.join(REPO_ROOT, "geospatial")

# --- FIRMS pipeline output (Person 1) --------------------------------------
# Frozen schema: anomaly_id, latitude, longitude, brightness, confidence,
# detections_30d, persistence_score, first_detected, last_detected,
# n_detections_total (see firms_pipeline.py).
FIRMS_PROCESSED_REAL = os.path.join(REPO_ROOT, "data", "processed", "firms_processed.csv")
FIRMS_PROCESSED_SAMPLE = os.path.join(REPO_ROOT, "firms_processed_sample.csv")

# --- Geospatial/OSM feature output (Person 2) ------------------------------
# Real schema (per geospatial/config.py OUTPUT_SCHEMA_COLUMNS): anomaly_id,
# latitude, longitude, nearest_industry, nearest_industry_name, distance_m,
# land_cover, nearest_forest_km. (population_proximity intentionally absent
# — see geospatial/config.py INCLUDE_POPULATION_PROXIMITY, Phase 1 audit.)
ANOMALY_FEATURES_REAL = os.path.join(REPO_ROOT, "data", "processed", "anomaly_features.csv")

# Mock stand-in Person 3 built and trained the model against while Person 2's
# real Overpass pull was blocked (see ml/README.md, ml/mock_features.py).
# Additionally includes a `population_proximity` column that the real
# pipeline does not produce — Phase 1 audit section E7.
ANOMALY_FEATURES_MOCK_FALLBACK = os.path.join(REPO_ROOT, "ml", "anomaly_features.csv")


def path_exists_and_nonempty(path: str) -> bool:
    """A `.gitkeep`-only directory or a zero-byte file should count as absent."""
    return os.path.isfile(path) and os.path.getsize(path) > 0
