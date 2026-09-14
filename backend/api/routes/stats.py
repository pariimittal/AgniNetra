"""
GET /api/stats — see backend/services/stats_service.py. Derived entirely
from the same events/facilities every other endpoint uses; no independent
or hard-coded numbers.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.data_access.anomaly_source import AnomalyDataUnavailable
from backend.ml_integration.pipeline_adapter import MLIntegrationError
from backend.schemas.stats import Stats
from backend.services import stats_service

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
def get_stats() -> dict:
    try:
        return stats_service.get_stats()
    except (AnomalyDataUnavailable, MLIntegrationError) as exc:
        raise HTTPException(status_code=503, detail=f"Stats are currently unavailable: {exc}") from exc
