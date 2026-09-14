"""
backend/tests/test_event_schema.py

Validates real event_service output against the Pydantic ThermalEvent
schema (backend/schemas/event.py). Requires `pydantic` to be installed —
see the Phase 3 report for whether this could actually be executed in the
development sandbox.

Run: pytest backend/tests/test_event_schema.py -v
"""

from __future__ import annotations

from backend.schemas.event import ThermalEvent
from backend.services import event_service


def setup_function() -> None:
    event_service._cached_events = None
    event_service._cached_annotated = None
    event_service._cached_baseline = None
    event_service._cached_source_info = None


def test_all_events_validate_against_thermal_event_schema() -> None:
    events = event_service.get_events()
    assert len(events) > 0
    for raw_event in events:
        # Raises pydantic.ValidationError on any type/shape mismatch.
        validated = ThermalEvent(**raw_event)
        assert validated.id == raw_event["id"]


def test_schema_round_trip_preserves_known_vocabulary() -> None:
    events = event_service.get_events()
    validated = [ThermalEvent(**e) for e in events[:5]]
    for event in validated:
        assert event.riskLevel in ("LOW", "MODERATE", "HIGH", "CRITICAL")
        assert event.thermalStatus in ("NORMAL", "MILDLY_ABNORMAL", "ABNORMAL")
        assert event.environmentalImpact in ("LOW", "MODERATE", "HIGH")
