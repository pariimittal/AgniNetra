"""
backend/ml_integration/pipeline_adapter.py

Thin, import-safe wrapper around the EXISTING `ml/pipeline.py` (Person 4's
already-built integration entry point, wiring classify_anomaly ->
get_fingerprint -> compute_risk). This module does not reimplement or
modify any classification/fingerprint/risk logic — it only solves the
working-directory coupling documented in the Phase 1 audit (section E10):

  - `ml/model.py` loads its trained artifacts with a bare relative path
    (`joblib.load("classification_model.pkl")`), which only resolves
    correctly if the process's cwd happens to be `ml/` at import time.
  - `ml/pipeline.py` does plain `import fingerprint` / `import risk` /
    `from model import classify_anomaly`, which only resolves if `ml/` is
    on `sys.path` (there's no `__init__.py` — it's a script folder, not a
    package).

Rather than requiring `uvicorn` to be launched from inside `ml/` (which the
Phase 3 spec explicitly forbids), this adapter:
  1. Adds `ml/` to `sys.path` (idempotently).
  2. Temporarily `os.chdir`s into `ml/` for the single moment `pipeline`
     (and transitively `model`) are first imported — this is when
     `classification_model.pkl` actually gets loaded — then restores the
     original cwd.
  3. Caches the imported module so this dance only happens once per process,
     not per request.

A module-level lock guards the one-time import so this is safe even if
multiple requests race to trigger the first import concurrently (FastAPI/
Starlette can run sync route code in a thread pool).
"""

from __future__ import annotations

import os
import sys
import threading
from types import ModuleType
from typing import Any

from backend.data_access.paths import ML_DIR

_import_lock = threading.Lock()
_pipeline_module: ModuleType | None = None


class MLIntegrationError(RuntimeError):
    """Raised when ml/pipeline.py (or its dependencies) cannot be imported."""


def _ensure_ml_dir_on_path() -> None:
    if ML_DIR not in sys.path:
        sys.path.insert(0, ML_DIR)


def _import_pipeline_module() -> ModuleType:
    """
    Import ml/pipeline.py exactly once, with `ml/` temporarily as the cwd so
    model.py's relative `joblib.load(...)` calls resolve correctly. Restores
    the original cwd afterwards regardless of success or failure.
    """
    global _pipeline_module
    if _pipeline_module is not None:
        return _pipeline_module

    with _import_lock:
        if _pipeline_module is not None:  # re-check after acquiring the lock
            return _pipeline_module

        if not os.path.isdir(ML_DIR):
            raise MLIntegrationError(f"ml/ directory not found at expected path: {ML_DIR}")

        _ensure_ml_dir_on_path()

        previous_cwd = os.getcwd()
        try:
            os.chdir(ML_DIR)
            import pipeline as ml_pipeline  # noqa: PLC0415 (deliberately lazy/local import)
        except Exception as exc:  # noqa: BLE001 — re-raised as our own error type
            raise MLIntegrationError(
                f"Failed to import ml/pipeline.py (and its dependencies "
                f"model.py/fingerprint.py/risk.py) with ml/ on sys.path and "
                f"cwd={ML_DIR}: {exc}"
            ) from exc
        finally:
            os.chdir(previous_cwd)

        _pipeline_module = ml_pipeline
        return _pipeline_module


def is_model_available() -> bool:
    """
    Mirrors ml/pipeline.py's own MODEL_AVAILABLE flag: True if Person 3's
    real trained model.py was importable, False if pipeline.py fell back to
    its built-in stub classifier (see ml/pipeline.py docstring).
    """
    module = _import_pipeline_module()
    return bool(module.MODEL_AVAILABLE)


def build_baseline(historical_anomalies: list[dict]) -> dict:
    """Wraps ml/pipeline.py's build_baseline_from_history()."""
    module = _import_pipeline_module()
    return module.build_baseline_from_history(historical_anomalies)


def process_anomaly(anomaly: dict, baseline: dict) -> dict[str, Any]:
    """Wraps ml/pipeline.py's process_anomaly() — see that module's
    docstring for the exact required input fields and output shape."""
    module = _import_pipeline_module()
    return module.process_anomaly(anomaly, baseline)


def get_fingerprint_module() -> ModuleType:
    """
    Returns the actual `ml/fingerprint.py` module (imported as an attribute
    of `ml/pipeline.py`, since pipeline.py does `import fingerprint`).

    Used by backend/services/facility_service.py to read already-computed
    baseline statistics (mean/std per facility or type group) straight out
    of the SAME baseline dict event_service builds — not to reimplement or
    re-derive fingerprint.py's abnormal/normal decision logic, which stays
    entirely inside ml/fingerprint.py.
    """
    module = _import_pipeline_module()
    return module.fingerprint


def get_fingerprint_constants() -> dict[str, float]:
    """
    Reads ml/fingerprint.py's own tunable constants (MIN_SAMPLES_FACILITY,
    MIN_SAMPLES_TYPE, ABNORMAL_Z_THRESHOLD, ZERO_STD_MARGIN) directly off
    the module, rather than hardcoding duplicate numbers in the backend
    that could silently drift out of sync if fingerprint.py's tuning ever
    changes. See ml/fingerprint.py's module docstring for what each means.
    """
    fp = get_fingerprint_module()
    return {
        "MIN_SAMPLES_FACILITY": fp.MIN_SAMPLES_FACILITY,
        "MIN_SAMPLES_TYPE": fp.MIN_SAMPLES_TYPE,
        "ABNORMAL_Z_THRESHOLD": fp.ABNORMAL_Z_THRESHOLD,
        "ZERO_STD_MARGIN": fp.ZERO_STD_MARGIN,
    }
