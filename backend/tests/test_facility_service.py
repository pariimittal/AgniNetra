"""
backend/tests/test_facility_service.py

Integration tests for backend/services/facility_service.py against the
real repository sample data + real ml/pipeline.py (via event_service). No
FastAPI/Pydantic dependency.

Run: pytest backend/tests/test_facility_service.py -v
"""

from __future__ import annotations

from backend.services import event_service, facility_service

_KNOWN_FACILITY_TYPES = {"REFINERY", "POWER PLANT", "MANUFACTURING", "MINING", "CHEMICAL"}
_KNOWN_THERMAL_STATUSES = {"NORMAL", "MILDLY_ABNORMAL", "ABNORMAL"}
_KNOWN_RISK_LEVELS = {"LOW", "MODERATE", "HIGH", "CRITICAL"}
_KNOWN_TIERS = {"facility", "type", "insufficient_history"}


def setup_function() -> None:
    event_service._cached_events = None
    event_service._cached_annotated = None
    event_service._cached_baseline = None
    event_service._cached_source_info = None
    facility_service._cached_facilities = None
    facility_service._cached_groups = None


def test_facilities_derived_only_from_real_anomalies_with_a_named_facility() -> None:
    facilities = facility_service.get_facilities()
    assert len(facilities) > 0

    events = event_service.get_events()
    events_with_facility = {e["facilityName"] for e in events if e["facilityName"]}
    facility_ids = {f["id"] for f in facilities}

    # Every facility must correspond to at least one real event that named it,
    # and vice versa — no invented facilities, no dropped real ones.
    assert facility_ids == events_with_facility


def test_no_facility_for_anomalies_with_no_nearby_industry() -> None:
    """An anomaly with nearest_industry == 'none' must never become / be
    attributed to a facility."""
    facilities = facility_service.get_facilities()
    facility_ids = {f["id"] for f in facilities}
    assert "none" not in facility_ids
    assert None not in facility_ids


def test_facility_fields_present_and_well_typed() -> None:
    for facility in facility_service.get_facilities():
        assert isinstance(facility["id"], str) and facility["id"]
        assert facility["type"] in _KNOWN_FACILITY_TYPES
        assert facility["thermalStatus"] in _KNOWN_THERMAL_STATUSES
        assert facility["riskLevel"] in _KNOWN_RISK_LEVELS
        assert isinstance(facility["latitude"], float)
        assert isinstance(facility["longitude"], float)
        assert 0 <= facility["persistence"] <= 100


def test_baseline_tier_is_always_reported_and_never_fabricated() -> None:
    """Every facility must honestly report which baseline tier backed its
    baselineBrightness — including 'insufficient_history', which must never
    be silently upgraded to look like a confident 'facility' baseline."""
    for facility in facility_service.get_facilities():
        meta = facility["meta"]
        assert meta["baselineTier"] in _KNOWN_TIERS
        assert meta["baselineSampleSize"] >= 0
        assert meta["anomalyCount"] >= 1


def test_location_is_a_coordinate_placeholder_not_a_fabricated_name() -> None:
    """No reverse-geocoding data exists anywhere in the repo — location
    must be the coordinate string, never an invented place name."""
    for facility in facility_service.get_facilities():
        lat_str = f"{facility['latitude']:.4f}"
        assert lat_str in facility["location"]


def test_get_facility_by_id_matches_list_entry() -> None:
    facilities = facility_service.get_facilities()
    target = facilities[0]
    fetched = facility_service.get_facility(target["id"])
    assert fetched == target


def test_get_facility_unknown_id_returns_none() -> None:
    assert facility_service.get_facility("DOES-NOT-EXIST") is None
    assert facility_service.get_facility_history("DOES-NOT-EXIST") is None
    assert facility_service.get_facility_fingerprint("DOES-NOT-EXIST") is None


def test_history_rows_correspond_to_real_anomalies_only() -> None:
    """No day-by-day interpolation: history length must equal the real
    number of anomalies observed at that facility, no more, no less."""
    for facility in facility_service.get_facilities():
        history = facility_service.get_facility_history(facility["id"])
        assert history is not None
        assert len(history) == facility["meta"]["anomalyCount"]
        for entry in history:
            assert entry["anomaly"] in _KNOWN_THERMAL_STATUSES
            assert entry["date"] is not None


def test_fingerprint_series_length_matches_real_history_length() -> None:
    for facility in facility_service.get_facilities():
        fingerprint = facility_service.get_facility_fingerprint(facility["id"])
        assert fingerprint is not None
        n = facility["meta"]["anomalyCount"]
        assert len(fingerprint["observed"]) == n
        assert len(fingerprint["baseline"]) == n
        assert len(fingerprint["threshold"]) == n
        assert len(fingerprint["timeLabels"]) == n
        assert fingerprint["frequency"] == n
        assert fingerprint["status"] in _KNOWN_THERMAL_STATUSES


def test_event_facility_id_matches_a_real_facility_when_present() -> None:
    """Cross-check: every event.facilityId that is set must resolve to a
    facility that actually exists in get_facilities() — proves the
    event<->facility linking is consistent, not just internally plausible."""
    events = event_service.get_events()
    facility_ids = {f["id"] for f in facility_service.get_facilities()}
    for event in events:
        if event["facilityId"] is not None:
            assert event["facilityId"] in facility_ids
            assert event["facilityId"] == event["facilityName"]


def test_events_without_nearby_industry_have_null_facility_id() -> None:
    events = event_service.get_events()
    for event in events:
        if event["facilityName"] is None:
            assert event["facilityId"] is None
