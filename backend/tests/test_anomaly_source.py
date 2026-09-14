"""
backend/tests/test_anomaly_source.py

Tests for backend/data_access/anomaly_source.py's real-vs-sample fallback
behavior. Depends on pandas only (no FastAPI/Pydantic needed).

Run: pytest backend/tests/test_anomaly_source.py -v
"""

from __future__ import annotations

import pytest

from backend.data_access import anomaly_source
from backend.data_access.paths import (
    ANOMALY_FEATURES_MOCK_FALLBACK,
    ANOMALY_FEATURES_REAL,
    FIRMS_PROCESSED_REAL,
    FIRMS_PROCESSED_SAMPLE,
)


def test_repo_committed_sample_files_exist() -> None:
    """Sanity check on the fixtures this whole test module relies on —
    if these ever go missing, every other test here would fail confusingly
    without this clearer signal first."""
    assert anomaly_source.path_exists_and_nonempty(FIRMS_PROCESSED_SAMPLE)
    assert anomaly_source.path_exists_and_nonempty(ANOMALY_FEATURES_MOCK_FALLBACK)


def test_real_processed_data_does_not_exist_yet() -> None:
    """As of Phase 1/3, data/processed/ only contains .gitkeep placeholders.
    This test documents that fact and will start failing (informatively)
    the moment someone actually runs the real FIRMS/geospatial pipelines —
    at which point test_falls_back_to_sample_when_real_absent below should
    be revisited too."""
    assert not anomaly_source.path_exists_and_nonempty(FIRMS_PROCESSED_REAL)
    assert not anomaly_source.path_exists_and_nonempty(ANOMALY_FEATURES_REAL)


def test_load_raw_anomalies_falls_back_to_sample_data() -> None:
    records, info = anomaly_source.load_raw_anomalies()

    assert len(records) > 0
    assert info.merged_row_count == len(records)

    # Given the current repo state (no real data/processed files), both
    # sources should resolve to the fallback sample/mock files.
    assert info.firms_is_real is False
    assert info.features_is_real is False
    assert info.firms_path == FIRMS_PROCESSED_SAMPLE
    assert info.features_path == ANOMALY_FEATURES_MOCK_FALLBACK


def test_loaded_records_have_no_fabricated_values() -> None:
    """Every anomaly_id / lat / lon / brightness / confidence must come
    straight from the committed sample CSV — this test cross-checks a known
    row's values against what's on disk rather than trusting the loader."""
    records, _ = anomaly_source.load_raw_anomalies()
    first = next(r for r in records if r["anomaly_id"] == "ANM0001")

    assert first["latitude"] == pytest.approx(29.26759)
    assert first["longitude"] == pytest.approx(86.29238)
    assert first["brightness"] == pytest.approx(344.1)
    assert first["confidence"] == pytest.approx(75.1)


def test_prefers_real_data_over_sample_when_present(tmp_path, monkeypatch) -> None:
    """Simulates a real data/processed/firms_processed.csv (and matching
    real anomaly_features.csv) existing, and confirms the loader prefers
    both over their sample/mock fallbacks.

    Note: the merge is an inner join on (anomaly_id, latitude, longitude),
    so the real firms file's rows must have a matching real features row to
    survive the merge — this is deliberate (see module docstring: we never
    fabricate geospatial context for an anomaly we don't have it for), so
    this test provides both real files rather than mixing a real firms file
    with the unrelated mock features file.
    """
    real_firms_csv = tmp_path / "firms_processed.csv"
    real_firms_csv.write_text(
        "anomaly_id,latitude,longitude,brightness,confidence,detections_30d,"
        "persistence_score,first_detected,last_detected,n_detections_total\n"
        "ANMREAL01,10.0,20.0,400.0,90.0,5,0.5,2026-01-01,2026-01-02,6\n"
    )
    real_features_csv = tmp_path / "anomaly_features.csv"
    real_features_csv.write_text(
        "anomaly_id,latitude,longitude,nearest_industry,nearest_industry_name,"
        "distance_m,land_cover,nearest_forest_km\n"
        "ANMREAL01,10.0,20.0,refinery,Real Refinery,120.0,industrial,5.0\n"
    )

    monkeypatch.setattr(anomaly_source, "FIRMS_PROCESSED_REAL", str(real_firms_csv))
    monkeypatch.setattr(anomaly_source, "ANOMALY_FEATURES_REAL", str(real_features_csv))

    records, info = anomaly_source.load_raw_anomalies()

    assert info.firms_is_real is True
    assert info.features_is_real is True
    assert info.firms_path == str(real_firms_csv)
    assert any(r["anomaly_id"] == "ANMREAL01" for r in records)


def test_raises_clear_error_when_no_data_available_at_all(monkeypatch) -> None:
    monkeypatch.setattr(anomaly_source, "FIRMS_PROCESSED_REAL", "/nonexistent/firms_real.csv")
    monkeypatch.setattr(anomaly_source, "FIRMS_PROCESSED_SAMPLE", "/nonexistent/firms_sample.csv")

    with pytest.raises(anomaly_source.AnomalyDataUnavailable):
        anomaly_source.load_raw_anomalies()


def test_raises_clear_error_on_schema_mismatch(tmp_path, monkeypatch) -> None:
    """If a 'real' file exists but doesn't match the frozen schema (missing
    merge-key columns), we must fail loudly rather than merge garbage."""
    bad_csv = tmp_path / "firms_processed.csv"
    bad_csv.write_text("not_the_right,columns_at_all\n1,2\n")

    monkeypatch.setattr(anomaly_source, "FIRMS_PROCESSED_REAL", str(bad_csv))

    with pytest.raises(anomaly_source.AnomalyDataUnavailable):
        anomaly_source.load_raw_anomalies()
