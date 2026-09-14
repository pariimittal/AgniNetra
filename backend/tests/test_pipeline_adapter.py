"""
backend/tests/test_pipeline_adapter.py

Tests for backend/ml_integration/pipeline_adapter.py. These exercise the
REAL ml/pipeline.py (Person 4's façade over ml/model.py, ml/fingerprint.py,
ml/risk.py) — nothing here is mocked out, by design, since the point of
this adapter is proving the real thing is importable and callable from the
repository root.

Depends on pandas/scikit-learn/joblib being installed (same as ml/ itself)
— NOT on FastAPI/Pydantic.

Run: pytest backend/tests/test_pipeline_adapter.py -v
"""

from __future__ import annotations

import os

from backend.data_access.paths import ML_DIR
from backend.ml_integration import pipeline_adapter


def test_ml_dir_resolves_to_a_real_directory() -> None:
    assert os.path.isdir(ML_DIR)
    assert os.path.isfile(os.path.join(ML_DIR, "pipeline.py"))
    assert os.path.isfile(os.path.join(ML_DIR, "classification_model.pkl"))


def test_import_does_not_require_running_from_ml_directory() -> None:
    """The whole point of this adapter: importing it must work regardless
    of the test runner's cwd (pytest is normally invoked from the repo
    root, i.e. NOT from inside ml/)."""
    cwd_before = os.getcwd()
    assert not cwd_before.rstrip(os.sep).endswith(os.sep + "ml")

    available = pipeline_adapter.is_model_available()

    assert isinstance(available, bool)
    # Import must not leave the process's cwd changed.
    assert os.getcwd() == cwd_before


def test_real_trained_model_is_available() -> None:
    """Distinguishes "imported fine but fell back to pipeline.py's stub
    classifier" from "the real trained classification_model.pkl loaded"."""
    assert pipeline_adapter.is_model_available() is True


def test_build_baseline_from_minimal_history() -> None:
    history = [
        {
            "brightness": 320.0,
            "detections_30d": 3,
            "persistence_score": 0.2,
            "nearest_industry": "none",
            "land_cover": "unknown",
        },
        {
            "brightness": 330.0,
            "detections_30d": 4,
            "persistence_score": 0.25,
            "nearest_industry": "none",
            "land_cover": "unknown",
        },
    ]
    baseline = pipeline_adapter.build_baseline(history)
    assert isinstance(baseline, dict)
    assert "facility" in baseline
    assert "type" in baseline


def test_process_one_real_sample_anomaly_end_to_end() -> None:
    """Feeds one real row (ANM0001) from the repo's own committed sample
    data through the real ml/pipeline.py, unmodified."""
    baseline = pipeline_adapter.build_baseline(
        [
            {
                "brightness": 340.0,
                "detections_30d": 6,
                "persistence_score": 0.5,
                "nearest_industry": "none",
                "land_cover": "residential",
            }
        ]
    )

    anomaly = {
        "id": "ANM0001",
        "lat": 29.26759,
        "lon": 86.29238,
        "source": "NASA FIRMS",
        "facility": None,
        "brightness": 344.1,
        "confidence": 75.1,
        "detections_30d": 7,
        "persistence_score": 0.54,
        "n_detections_total": 14,
        "distance_m": 16719.4,
        "nearest_forest_km": 1.79,
        "nearest_industry": "none",
        "land_cover": "residential",
    }

    result = pipeline_adapter.process_anomaly(anomaly, baseline)

    assert result["id"] == "ANM0001"
    assert "classification" in result
    assert "confidence" in result
    assert 0 <= result["confidence"] <= 100
    assert "thermal_status" in result
    assert "risk_score" in result
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert "environmental_impact" in result


def test_second_call_reuses_cached_module_import() -> None:
    """After the first call above, re-importing must be a no-op (cached),
    not re-trigger the chdir dance or reload the pickled model."""
    module_before = pipeline_adapter._pipeline_module
    assert module_before is not None
    pipeline_adapter.is_model_available()
    assert pipeline_adapter._pipeline_module is module_before
