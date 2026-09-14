"""
GET /api/facilities
GET /api/facilities/{facility_id}
GET /api/facilities/{facility_id}/history
GET /api/facilities/{facility_id}/fingerprint

See backend/services/facility_service.py for exactly how facilities are
derived from real anomaly data (there is no separate facility database
anywhere in this repository) and which fields are documented
approximations vs. genuinely measured values.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.data_access.anomaly_source import AnomalyDataUnavailable
from backend.ml_integration.pipeline_adapter import MLIntegrationError
from backend.schemas.facility import Facility, FacilityHistoryEntry, FingerprintData
from backend.services import facility_service

router = APIRouter(tags=["facilities"])


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Facility data is currently unavailable: {exc}")


@router.get("/facilities", response_model=list[Facility])
def list_facilities() -> list[dict]:
    try:
        return facility_service.get_facilities()
    except (AnomalyDataUnavailable, MLIntegrationError) as exc:
        raise _unavailable(exc) from exc


@router.get("/facilities/{facility_id}", response_model=Facility)
def get_facility(facility_id: str) -> dict:
    try:
        facility = facility_service.get_facility(facility_id)
    except (AnomalyDataUnavailable, MLIntegrationError) as exc:
        raise _unavailable(exc) from exc

    if facility is None:
        raise HTTPException(status_code=404, detail=f"No facility found with id '{facility_id}'.")
    return facility


@router.get("/facilities/{facility_id}/history", response_model=list[FacilityHistoryEntry])
def get_facility_history(facility_id: str) -> list[dict]:
    try:
        history = facility_service.get_facility_history(facility_id)
    except (AnomalyDataUnavailable, MLIntegrationError) as exc:
        raise _unavailable(exc) from exc

    if history is None:
        raise HTTPException(status_code=404, detail=f"No facility found with id '{facility_id}'.")
    return history


@router.get("/facilities/{facility_id}/fingerprint", response_model=FingerprintData)
def get_facility_fingerprint(facility_id: str) -> dict:
    try:
        fingerprint = facility_service.get_facility_fingerprint(facility_id)
    except (AnomalyDataUnavailable, MLIntegrationError) as exc:
        raise _unavailable(exc) from exc

    if fingerprint is None:
        raise HTTPException(status_code=404, detail=f"No facility found with id '{facility_id}'.")
    return fingerprint
