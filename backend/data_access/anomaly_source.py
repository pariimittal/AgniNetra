"""
backend/data_access/anomaly_source.py

Loads and merges the two upstream, independently-produced datasets that
together describe a thermal anomaly:

  - Person 1's FIRMS output   (firms_processed.csv / frozen schema)
  - Person 2's geospatial/OSM feature output (anomaly_features.csv)

and hands back a list of plain dicts ready to feed into the ML pipeline
(backend/ml_integration). This module does NOT call the ML pipeline and
does NOT know anything about the frontend's ThermalEvent shape — it only
answers "what raw anomaly data exists in this repository right now?"

FALLBACK BEHAVIOUR (per Phase 1 audit — no real processed data exists yet):
  - firms:    data/processed/firms_processed.csv (real) if present,
              else firms_processed_sample.csv (repo root sample).
  - features: data/processed/anomaly_features.csv (real) if present,
              else ml/anomaly_features.csv (Person 3's mock stand-in,
              per ml/README.md — includes population_proximity, which the
              real pipeline does not produce; see Phase 1 audit section E7).

We do NOT fabricate any anomaly data ourselves — every row returned here
came from files already committed to the repository by the team.

If NEITHER a firms file NOR a features file can be found at all, this
raises `AnomalyDataUnavailable` rather than crashing the process or
inventing placeholder rows — callers (the event service / API routes) are
expected to turn that into a clear 503 rather than a 500 or a silent [].
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.data_access.paths import (
    ANOMALY_FEATURES_MOCK_FALLBACK,
    ANOMALY_FEATURES_REAL,
    FIRMS_PROCESSED_REAL,
    FIRMS_PROCESSED_SAMPLE,
    path_exists_and_nonempty,
)

MERGE_KEYS = ["anomaly_id", "latitude", "longitude"]


class AnomalyDataUnavailable(RuntimeError):
    """Raised when no usable FIRMS and/or feature data can be located at all."""


@dataclass(frozen=True)
class AnomalyDataSourceInfo:
    """Which files were actually used to build the merged anomaly set, and
    whether they're the real pipeline's output or a fallback sample/mock —
    useful for logging and for any future /api/health or /api/stats work
    that wants to be honest with the frontend about data provenance."""

    firms_path: str
    firms_is_real: bool
    features_path: str
    features_is_real: bool
    firms_row_count: int
    features_row_count: int
    merged_row_count: int


def _resolve_firms_path() -> tuple[str, bool]:
    if path_exists_and_nonempty(FIRMS_PROCESSED_REAL):
        return FIRMS_PROCESSED_REAL, True
    if path_exists_and_nonempty(FIRMS_PROCESSED_SAMPLE):
        return FIRMS_PROCESSED_SAMPLE, False
    raise AnomalyDataUnavailable(
        f"No FIRMS data found. Checked real path ({FIRMS_PROCESSED_REAL}) "
        f"and sample fallback ({FIRMS_PROCESSED_SAMPLE}). Run "
        "firms_pipeline.py (--mock is fine for local dev) before starting "
        "the backend, or restore firms_processed_sample.csv."
    )


def _resolve_features_path() -> tuple[str, bool]:
    if path_exists_and_nonempty(ANOMALY_FEATURES_REAL):
        return ANOMALY_FEATURES_REAL, True
    if path_exists_and_nonempty(ANOMALY_FEATURES_MOCK_FALLBACK):
        return ANOMALY_FEATURES_MOCK_FALLBACK, False
    raise AnomalyDataUnavailable(
        f"No geospatial feature data found. Checked real path "
        f"({ANOMALY_FEATURES_REAL}) and mock fallback "
        f"({ANOMALY_FEATURES_MOCK_FALLBACK}). Run geospatial/run_features.py "
        "(needs network access to Overpass) or restore ml/anomaly_features.csv."
    )


def load_raw_anomalies() -> tuple[list[dict], AnomalyDataSourceInfo]:
    """
    Load, merge, and return every anomaly this repository currently has data
    for, as a list of plain dicts (pandas types converted to native Python /
    JSON-safe values), plus metadata about which files were used.

    Raises AnomalyDataUnavailable if no usable input files exist at all.
    Returns an empty list (not an error) if the files exist but the merge
    produces zero matching rows — that's a legitimate "no data yet" state,
    not a crash.
    """
    firms_path, firms_is_real = _resolve_firms_path()
    features_path, features_is_real = _resolve_features_path()

    firms_df = pd.read_csv(firms_path)
    features_df = pd.read_csv(features_path)

    missing_firms_cols = set(MERGE_KEYS) - set(firms_df.columns)
    if missing_firms_cols:
        raise AnomalyDataUnavailable(
            f"{firms_path} is missing required columns {missing_firms_cols}; "
            "it does not match the frozen FIRMS schema documented in "
            "firms_pipeline.py."
        )
    missing_feature_cols = set(MERGE_KEYS) - set(features_df.columns)
    if missing_feature_cols:
        raise AnomalyDataUnavailable(
            f"{features_path} is missing required columns {missing_feature_cols}; "
            "it does not match the schema documented in geospatial/config.py."
        )

    merged_df = firms_df.merge(features_df, on=MERGE_KEYS, how="inner")

    # NaN -> None so downstream JSON/Pydantic serialization never chokes on
    # float('nan') (e.g. nearest_forest_km can legitimately be NaN — see
    # geospatial/features.py nearest_forest_km() when no forest polygon
    # exists in the fetched landuse data).
    merged_df = merged_df.where(pd.notnull(merged_df), None)

    records = merged_df.to_dict(orient="records")

    info = AnomalyDataSourceInfo(
        firms_path=firms_path,
        firms_is_real=firms_is_real,
        features_path=features_path,
        features_is_real=features_is_real,
        firms_row_count=len(firms_df),
        features_row_count=len(features_df),
        merged_row_count=len(records),
    )
    return records, info
