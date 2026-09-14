"""
backend/tests/test_api_routes.py

End-to-end HTTP-level tests for every route wired into backend/main.py.
Requires fastapi + pydantic (not available in the development sandbox this
was written in — see the Phase 4 report for what could/couldn't actually be
executed here).

Run: pytest backend/tests/test_api_routes.py -v
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import event_service, facility_service

client = TestClient(app)


def setup_function() -> None:
    event_service._cached_events = None
    event_service._cached_annotated = None
    event_service._cached_baseline = None
    event_service._cached_source_info = None
    facility_service._cached_facilities = None
    facility_service._cached_groups = None


# --- health -----------------------------------------------------------------


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "live"}


# --- events -------------------------------------------------------------


def test_list_events_200_and_nonempty() -> None:
    response = client.get("/api/events")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_get_event_by_real_id() -> None:
    events = client.get("/api/events").json()
    target_id = events[0]["id"]
    response = client.get(f"/api/events/{target_id}")
    assert response.status_code == 200
    assert response.json()["id"] == target_id


def test_get_event_unknown_id_404() -> None:
    response = client.get("/api/events/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_events_deterministic_across_requests() -> None:
    first = client.get("/api/events").json()
    second = client.get("/api/events").json()
    assert first == second


# --- facilities -----------------------------------------------------------


def test_list_facilities_200_and_nonempty() -> None:
    response = client.get("/api/facilities")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_get_facility_by_real_id() -> None:
    facilities = client.get("/api/facilities").json()
    target_id = facilities[0]["id"]
    response = client.get(f"/api/facilities/{target_id}")
    assert response.status_code == 200
    assert response.json()["id"] == target_id


def test_get_facility_unknown_id_404() -> None:
    response = client.get("/api/facilities/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_facility_history_200_for_real_facility() -> None:
    facilities = client.get("/api/facilities").json()
    target_id = facilities[0]["id"]
    response = client.get(f"/api/facilities/{target_id}/history")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1


def test_facility_history_unknown_id_404() -> None:
    response = client.get("/api/facilities/DOES-NOT-EXIST/history")
    assert response.status_code == 404


def test_facility_fingerprint_200_for_real_facility() -> None:
    facilities = client.get("/api/facilities").json()
    target_id = facilities[0]["id"]
    response = client.get(f"/api/facilities/{target_id}/fingerprint")
    assert response.status_code == 200
    body = response.json()
    assert body["facilityId"] == target_id


def test_facility_fingerprint_unknown_id_404() -> None:
    response = client.get("/api/facilities/DOES-NOT-EXIST/fingerprint")
    assert response.status_code == 404


# --- stats ------------------------------------------------------------------


def test_stats_200_and_shape() -> None:
    response = client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"thermalEvents", "abnormal", "highCritical", "facilitiesMonitored"}


def test_stats_matches_live_events_and_facilities_counts() -> None:
    stats = client.get("/api/stats").json()
    events = client.get("/api/events").json()
    facilities = client.get("/api/facilities").json()
    assert stats["thermalEvents"] == len(events)
    assert stats["facilitiesMonitored"] == len(facilities)


# --- event <-> facility linking ----------------------------------------------


def test_every_event_facility_id_resolves_to_a_real_facility() -> None:
    events = client.get("/api/events").json()
    facility_ids = {f["id"] for f in client.get("/api/facilities").json()}
    for event in events:
        if event["facilityId"] is not None:
            assert event["facilityId"] in facility_ids
