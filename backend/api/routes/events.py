"""
GET /api/events
GET /api/events/{event_id}

Serves real thermal-anomaly events built from the repository's own FIRMS +
geospatial data, run through the existing ml/pipeline.py (classification ->
fingerprint -> risk), and translated into the frontend's ThermalEvent shape
(see backend/services/event_service.py and backend/services/mapping.py for
exactly how).

Errors are surfaced deliberately rather than silently returning an empty
list or fabricated data:
  - Missing/unusable upstream data (no FIRMS or geospatial files at all, or
    the ML pipeline can't be imported) -> HTTP 503, not a 500 crash and not
    a quiet [].
  - Unknown event id -> HTTP 404.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.data_access.anomaly_source import AnomalyDataUnavailable
from backend.ml_integration.pipeline_adapter import MLIntegrationError
from backend.schemas.event import ThermalEvent
from backend.services import event_service

router = APIRouter(tags=["events"])


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            "Thermal event data is currently unavailable: "
            f"{exc}"
        ),
    )


@router.get("/events", response_model=list[ThermalEvent])
def list_events() -> list[dict]:
    try:
        return event_service.get_events()
    except (AnomalyDataUnavailable, MLIntegrationError) as exc:
        raise _unavailable(exc) from exc


@router.get("/events/{event_id}", response_model=ThermalEvent)
def get_event(event_id: str) -> dict:
    try:
        event = event_service.get_event(event_id)
    except (AnomalyDataUnavailable, MLIntegrationError) as exc:
        raise _unavailable(exc) from exc

    if event is None:
        raise HTTPException(status_code=404, detail=f"No thermal event found with id '{event_id}'.")
    return event
