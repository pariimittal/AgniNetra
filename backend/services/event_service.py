"""
backend/services/event_service.py

Orchestration layer for GET /api/events and GET /api/events/{id}. Wires
together (without modifying any of them):

  backend.data_access.anomaly_source.load_raw_anomalies()
      -> real/sample-merged FIRMS + geospatial rows
  backend.ml_integration.pipeline_adapter
      -> ml/pipeline.py's build_baseline_from_history() / process_anomaly()
  backend.services.mapping
      -> translates pipeline output into the frontend's ThermalEvent shape

CACHING
-------
Building the full event list re-runs classification + fingerprinting +
risk scoring for every anomaly, which is unnecessary work to repeat on
every request against a static, in-repo dataset. Results are cached
in-process after the first successful build. `refresh_events()` is exposed
so a future phase (e.g. a real FIRMS data refresh) can invalidate this
without restarting the process. This is intentionally a simple in-memory
cache — no external cache/store — appropriate for this phase's scope.

If the upstream data or ML pipeline can't be loaded, `AnomalyDataUnavailable`
/ `MLIntegrationError` propagate up to the route layer, which is
responsible for turning them into a clean HTTP 503 rather than a 500.
"""

from __future__ import annotations

import threading
from typing import Any

from backend.data_access.anomaly_source import AnomalyDataSourceInfo, load_raw_anomalies
from backend.ml_integration import pipeline_adapter
from backend.services import mapping

_cache_lock = threading.Lock()
_cached_events: list[dict[str, Any]] | None = None
_cached_annotated: list[dict[str, Any]] | None = None
_cached_baseline: dict[str, Any] | None = None
_cached_source_info: AnomalyDataSourceInfo | None = None


def _build_pipeline_input(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Maps one merged FIRMS+geospatial row (backend.data_access shape) onto
    the exact input dict ml/pipeline.py's process_anomaly() expects (see
    that module's docstring / Phase 1 audit section D).
    """
    nearest_industry = raw.get("nearest_industry") or "none"
    facility_name = raw.get("nearest_industry_name")
    has_facility = nearest_industry != "none" and bool(facility_name) and facility_name != "unnamed"

    return {
        "id": raw["anomaly_id"],
        "lat": raw["latitude"],
        "lon": raw["longitude"],
        "source": "NASA FIRMS",
        "facility": facility_name if has_facility else None,
        "brightness": raw.get("brightness"),
        "confidence": raw.get("confidence"),
        "detections_30d": raw.get("detections_30d"),
        "persistence_score": raw.get("persistence_score"),
        "n_detections_total": raw.get("n_detections_total"),
        "distance_m": raw.get("distance_m"),
        "nearest_forest_km": raw.get("nearest_forest_km"),
        "nearest_industry": nearest_industry,
        "land_cover": raw.get("land_cover") or "unknown",
    }


def _build_thermal_event(raw: dict[str, Any], pipeline_result: dict[str, Any]) -> dict[str, Any]:
    """Combines the raw merged row + ml/pipeline.py output into the
    frontend's ThermalEvent shape, via backend.services.mapping for every
    vocabulary translation (see that module for what's real vs. derived)."""

    classification = mapping.map_classification(pipeline_result.get("classification"))
    risk_score = int(pipeline_result.get("risk_score", 0))
    risk_level = mapping.map_risk_level(risk_score)

    thermal_tier = pipeline_result.get("thermal_tier", "none")
    thermal_status_raw = pipeline_result.get("thermal_status", "Insufficient History")
    thermal_status = mapping.map_thermal_status(thermal_status_raw, thermal_tier)

    risk_components = mapping.map_risk_components(pipeline_result.get("risk_breakdown", {}))
    deviation_score = risk_components["deviation"]

    nearest_industry = raw.get("nearest_industry") or "none"
    has_facility = nearest_industry != "none"
    facility_name = raw.get("nearest_industry_name") if has_facility else None

    # facilityId uses the SAME identifier backend/services/facility_service.py
    # assigns a facility (its raw nearest_industry_name) — see that module's
    # docstring for why this placeholder-but-stable id scheme was chosen.
    # Keeping the two in lockstep is what lets the frontend's
    # `facilities.find(item => item.id === event.facilityId)`-style lookups
    # (see src/App.tsx EventDetailPage) actually resolve.
    facility_id = facility_name if has_facility else None

    # These two aren't produced anywhere upstream yet (see mapping.py
    # docstring) — pipeline_result doesn't carry a fingerprint dict of its
    # own for us to read triggered_by/details from, so we reconstruct a
    # minimal one from what process_anomaly() DID pass through.
    fingerprint_like = {
        "triggered_by": [],  # not exposed by pipeline.process_anomaly()'s return shape
        "details": pipeline_result.get("thermal_details"),
    }

    event = {
        "id": raw["anomaly_id"],
        "timestamp": f"{raw.get('last_detected')}T00:00:00Z" if raw.get("last_detected") else None,
        "latitude": raw["latitude"],
        "longitude": raw["longitude"],
        "brightness": raw.get("brightness"),
        "confidence": raw.get("confidence"),
        "facilityId": facility_id,
        "facilityName": facility_name,
        "facilityType": nearest_industry if has_facility else None,
        "distanceToFacility": (
            round(raw["distance_m"] / 1000.0, 2)
            if has_facility and raw.get("distance_m") is not None
            else None
        ),
        "classification": classification,
        "classificationConfidence": pipeline_result.get("confidence", 0),
        "thermalStatus": thermal_status,
        "deviationScore": deviation_score,
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "lifecycle": mapping.map_lifecycle(raw.get("persistence_score"), raw.get("n_detections_total")),
        "detectionCount": raw.get("detections_30d", 0),
        "environmentalImpact": mapping.map_environmental_impact(pipeline_result.get("environmental_impact")),
        "riskReasons": mapping.build_risk_reasons(pipeline_result, classification),
        "deviationReasons": mapping.build_deviation_reasons(fingerprint_like),
        "riskComponents": risk_components,
        # Additional, non-breaking fields beyond the frontend's ThermalEvent
        # TS type. TS interfaces aren't runtime-validated, so extra JSON
        # keys are simply ignored by the current UI — these exist so a
        # future UI/debugging pass doesn't have to re-derive lossy-mapping
        # provenance from scratch. See mapping.py module docstring.
        "pipelineMeta": {
            "thermalStatusRaw": thermal_status_raw,
            "thermalTier": thermal_tier,
            "thermalDetails": pipeline_result.get("thermal_details"),
            "classificationRaw": pipeline_result.get("classification"),
            "classificationReliability": pipeline_result.get("classification_reliability"),
            "riskLevelRaw": pipeline_result.get("risk_level"),
            "riskBreakdown": pipeline_result.get("risk_breakdown"),
        },
    }
    return event


def _build_all_events() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], AnomalyDataSourceInfo]:
    raw_records, source_info = load_raw_anomalies()

    # Baseline is built once from the full available anomaly set (there is
    # no separate "historical" dataset yet — every anomaly we have IS the
    # history). See ml/fingerprint.py's build_baseline docstring for the
    # facility/type two-tier grouping this feeds into.
    baseline = pipeline_adapter.build_baseline(raw_records)

    events: list[dict[str, Any]] = []
    annotated: list[dict[str, Any]] = []
    for raw in raw_records:
        pipeline_input = _build_pipeline_input(raw)
        pipeline_result = pipeline_adapter.process_anomaly(pipeline_input, baseline)
        event = _build_thermal_event(raw, pipeline_result)
        events.append(event)
        annotated.append({"raw": raw, "pipeline_result": pipeline_result, "event": event})

    return events, annotated, baseline, source_info


def _ensure_built() -> None:
    global _cached_events, _cached_annotated, _cached_baseline, _cached_source_info
    if _cached_events is not None:
        return
    with _cache_lock:
        if _cached_events is None:  # re-check after acquiring the lock
            events, annotated, baseline, source_info = _build_all_events()
            _cached_events = events
            _cached_annotated = annotated
            _cached_baseline = baseline
            _cached_source_info = source_info


def get_events() -> list[dict[str, Any]]:
    """Returns the full list of ThermalEvent-shaped dicts, building and
    caching them on first call. Raises AnomalyDataUnavailable or
    MLIntegrationError if the underlying data/pipeline can't be loaded."""
    _ensure_built()
    assert _cached_events is not None
    return _cached_events


def get_event(event_id: str) -> dict[str, Any] | None:
    """Returns a single ThermalEvent-shaped dict by id, or None if not found."""
    for event in get_events():
        if event["id"] == event_id:
            return event
    return None


def get_annotated_events() -> list[dict[str, Any]]:
    """
    Returns, for every anomaly, the raw merged FIRMS+geospatial row AND the
    raw ml/pipeline.py output AND the final mapped ThermalEvent dict,
    together as {"raw": ..., "pipeline_result": ..., "event": ...}.

    Exists so backend/services/facility_service.py can aggregate anomalies
    into facilities WITHOUT re-running the ML pipeline a second time — it
    reuses exactly the same per-anomaly classification/fingerprint/risk
    results already computed here, per the Phase 4 instruction to reuse
    event_service rather than duplicate processing logic.
    """
    _ensure_built()
    assert _cached_annotated is not None
    return _cached_annotated


def get_baseline() -> dict[str, Any]:
    """Returns the same baseline dict (ml/fingerprint.py's build_baseline()
    output) used to compute every event, so facility_service can read
    facility-level/type-level (mean, std, n) directly instead of
    re-deriving it."""
    _ensure_built()
    assert _cached_baseline is not None
    return _cached_baseline


def get_source_info() -> AnomalyDataSourceInfo | None:
    """Returns metadata about which data files backed the current cache
    (None if get_events() hasn't been called yet). Not exposed via any
    route in this phase — available for future /api/health or /api/stats
    work, and useful for debugging."""
    return _cached_source_info


def refresh_events() -> list[dict[str, Any]]:
    """Forces a rebuild of the cached event list (e.g. after new upstream
    data lands). Not wired to any route yet in this phase."""
    global _cached_events, _cached_annotated, _cached_baseline, _cached_source_info
    with _cache_lock:
        events, annotated, baseline, source_info = _build_all_events()
        _cached_events = events
        _cached_annotated = annotated
        _cached_baseline = baseline
        _cached_source_info = source_info
    return _cached_events
