"""
backend/tests/test_stats_service.py

Run: pytest backend/tests/test_stats_service.py -v
"""

from __future__ import annotations

from backend.services import event_service, facility_service, stats_service


def setup_function() -> None:
    event_service._cached_events = None
    event_service._cached_annotated = None
    event_service._cached_baseline = None
    event_service._cached_source_info = None
    facility_service._cached_facilities = None
    facility_service._cached_groups = None


def test_stats_shape() -> None:
    stats = stats_service.get_stats()
    assert set(stats.keys()) == {"thermalEvents", "abnormal", "highCritical", "facilitiesMonitored"}
    for value in stats.values():
        assert isinstance(value, int)
        assert value >= 0


def test_stats_thermal_events_matches_real_event_count() -> None:
    stats = stats_service.get_stats()
    assert stats["thermalEvents"] == len(event_service.get_events())


def test_stats_facilities_monitored_matches_real_facility_count() -> None:
    stats = stats_service.get_stats()
    assert stats["facilitiesMonitored"] == len(facility_service.get_facilities())


def test_stats_abnormal_count_matches_manual_count() -> None:
    events = event_service.get_events()
    expected = sum(1 for e in events if e["thermalStatus"] == "ABNORMAL")
    assert stats_service.get_stats()["abnormal"] == expected


def test_stats_high_critical_matches_manual_count() -> None:
    events = event_service.get_events()
    expected = sum(1 for e in events if e["riskLevel"] in ("HIGH", "CRITICAL"))
    assert stats_service.get_stats()["highCritical"] == expected


def test_stats_are_deterministic_across_calls() -> None:
    assert stats_service.get_stats() == stats_service.get_stats()
