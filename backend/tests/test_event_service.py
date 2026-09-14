"""
backend/tests/test_event_service.py

End-to-end integration tests for backend/services/event_service.py — the
full chain: real sample data -> real ml/pipeline.py -> mapping adapter ->
ThermalEvent-shaped dicts. No FastAPI/Pydantic dependency (event_service
itself doesn't import either).

Run: pytest backend/tests/test_event_service.py -v
"""

from __future__ import annotations

from backend.services import event_service

# ThermalEvent required keys per src/types/index.ts (see
# backend/schemas/event.py for the Pydantic mirror of the same contract).
_REQUIRED_KEYS = {
    "id",
    "latitude",
    "longitude",
    "classification",
    "classificationConfidence",
    "thermalStatus",
    "deviationScore",
    "riskScore",
    "riskLevel",
    "lifecycle",
    "detectionCount",
    "environmentalImpact",
    "riskReasons",
    "deviationReasons",
    "riskComponents",
}

_KNOWN_CLASSIFICATIONS = {
    "Industrial Fire",
    "Gas Flare / Persistent Source",
    "Wildfire",
    "Agricultural Burning",
    "Mining Activity",
    "Unknown",
}
_KNOWN_RISK_LEVELS = {"LOW", "MODERATE", "HIGH", "CRITICAL"}
_KNOWN_THERMAL_STATUSES = {"NORMAL", "MILDLY_ABNORMAL", "ABNORMAL"}
_KNOWN_ENV_IMPACTS = {"LOW", "MODERATE", "HIGH"}


def setup_function() -> None:
    # Each test gets a clean cache so ordering between test files doesn't matter.
    event_service._cached_events = None
    event_service._cached_annotated = None
    event_service._cached_baseline = None
    event_service._cached_source_info = None


def test_get_events_returns_real_sample_backed_events() -> None:
    events = event_service.get_events()
    assert len(events) > 0

    source_info = event_service.get_source_info()
    assert source_info is not None
    assert source_info.merged_row_count == len(events)


def test_every_event_has_required_frontend_fields() -> None:
    events = event_service.get_events()
    for event in events:
        missing = _REQUIRED_KEYS - event.keys()
        assert not missing, f"event {event.get('id')} missing keys: {missing}"


def test_every_event_uses_only_known_vocabulary() -> None:
    events = event_service.get_events()
    for event in events:
        assert event["classification"] in _KNOWN_CLASSIFICATIONS, event["classification"]
        assert event["riskLevel"] in _KNOWN_RISK_LEVELS, event["riskLevel"]
        assert event["thermalStatus"] in _KNOWN_THERMAL_STATUSES, event["thermalStatus"]
        assert event["environmentalImpact"] in _KNOWN_ENV_IMPACTS, event["environmentalImpact"]


def test_every_event_numeric_fields_in_range() -> None:
    events = event_service.get_events()
    for event in events:
        assert 0 <= event["riskScore"] <= 100
        assert 0 <= event["deviationScore"] <= 100
        assert 0 <= event["classificationConfidence"] <= 100
        for value in event["riskComponents"].values():
            assert 0 <= value <= 100


def test_gas_flare_alias_reaches_the_final_event_when_present() -> None:
    """The trained model does emit the literal label 'Gas Flare' on at
    least one row of the repo's own training data (Phase 1 audit finding);
    if the raw pipeline ever classifies an anomaly that way, the final
    event must show the frontend's canonical label, never the raw one."""
    events = event_service.get_events()
    raw_labels = {e["pipelineMeta"]["classificationRaw"] for e in events if e.get("pipelineMeta")}
    final_labels = {e["classification"] for e in events}

    assert "Gas Flare" not in final_labels
    if "Gas Flare" in raw_labels:
        assert "Gas Flare / Persistent Source" in final_labels


def test_get_event_by_id_matches_list_entry() -> None:
    events = event_service.get_events()
    target = events[0]
    fetched = event_service.get_event(target["id"])
    assert fetched == target


def test_get_event_unknown_id_returns_none() -> None:
    assert event_service.get_event("DOES-NOT-EXIST") is None


def test_events_are_cached_not_recomputed_on_second_call() -> None:
    first = event_service.get_events()
    second = event_service.get_events()
    assert first is second  # same list object, not just equal


def test_refresh_events_rebuilds_the_cache() -> None:
    first = event_service.get_events()
    second = event_service.refresh_events()
    assert first is not second
    assert len(first) == len(second)


def test_no_fabricated_coordinates_or_brightness() -> None:
    """Cross-check the final event's raw physical fields against the known
    committed sample row for ANM0001 (Phase 1 audit's traced values)."""
    events = event_service.get_events()
    anm0001 = next(e for e in events if e["id"] == "ANM0001")
    assert anm0001["latitude"] == 29.26759
    assert anm0001["longitude"] == 86.29238
    assert anm0001["brightness"] == 344.1
    assert anm0001["confidence"] == 75.1
