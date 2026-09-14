"""
GET /api/health

Simple liveness/mode indicator consumed by the frontend's `getHealth()`
(src/api/client.ts). The frontend already tolerates this endpoint being
unreachable (falls back to {status: 'OPERATIONAL', mode: 'demo'}), so this
route just needs to exist and return a well-formed, fast response.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import get_settings
from backend.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", mode=settings.api_mode)  # type: ignore[arg-type]
