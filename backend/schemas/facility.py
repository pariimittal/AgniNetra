"""
backend/schemas/facility.py

Pydantic response schemas for GET /api/facilities, GET /api/facilities/{id},
GET /api/facilities/{id}/history, and GET /api/facilities/{id}/fingerprint.
Field names/types mirror the frontend's `Facility`, `FacilityHistory`, and
`FingerprintData` types exactly (src/types/index.ts).

`meta` blocks on Facility and FingerprintData are ADDITIONAL fields beyond
the frontend's TS types (harmless extra JSON keys — TS interfaces aren't
runtime-validated). They exist so "insufficient history" / which baseline
tier was used is never silently hidden — see
backend/services/facility_service.py's module docstring.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

FacilityType = Literal["REFINERY", "POWER PLANT", "MANUFACTURING", "MINING", "CHEMICAL"]
ThermalStatus = Literal["NORMAL", "MILDLY_ABNORMAL", "ABNORMAL"]
RiskLevel = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
BaselineTier = Literal["facility", "type", "insufficient_history"]


class FacilityMeta(BaseModel):
    baselineTier: BaselineTier
    baselineSampleSize: int
    anomalyCount: int
    normalWindowLow: float
    normalWindowHigh: float


class Facility(BaseModel):
    id: str
    name: str
    type: FacilityType
    location: str
    latitude: float
    longitude: float
    baselineBrightness: float
    currentBrightness: float | None = None
    detections30d: int
    persistence: float
    thermalStatus: ThermalStatus
    normalWindow: str
    riskLevel: RiskLevel
    meta: FacilityMeta | None = None


class FacilityHistoryEntry(BaseModel):
    date: str | None = None
    observedBrightness: float | None = None
    baseline: float
    threshold: float
    detectionCount: int
    normalWindow: str
    anomaly: ThermalStatus


class FingerprintData(BaseModel):
    facilityId: str
    observed: list[float | None]
    baseline: list[float]
    threshold: list[float]
    timeLabels: list[str | None]
    typicalWindow: str
    frequency: int
    persistence: float
    currentValue: float
    delta: float
    status: ThermalStatus
    meta: FacilityMeta | None = None
