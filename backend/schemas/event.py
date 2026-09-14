"""
backend/schemas/event.py

Pydantic response schema for GET /api/events and GET /api/events/{id}.
Field names and types mirror the frontend's `ThermalEvent` type exactly
(src/types/index.ts) — do not rename fields here without also updating the
frontend, since these are serialized as camelCase JSON keys the UI reads
directly.

`PipelineMeta` is an ADDITIONAL block beyond the frontend's TS type. TS
interfaces aren't runtime-validated, so extra JSON keys are harmless to the
current UI — this exists to preserve full fidelity of the underlying
ml/pipeline.py output (raw thermal status/tier, raw classification, raw
risk level, full risk breakdown) for debugging and future phases, rather
than silently discarding it once it's been lossily mapped. See
backend/services/mapping.py's module docstring for exactly which fields on
ThermalEvent are lossy/approximate translations vs. real pipeline output.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
ThermalStatus = Literal["NORMAL", "MILDLY_ABNORMAL", "ABNORMAL"]
LifecycleState = Literal["FIRST_SEEN", "GROWING", "PERSISTENT", "DECLINING", "REIGNITED", "RESOLVED"]
EnvironmentalImpact = Literal["LOW", "MODERATE", "HIGH"]


class RiskComponents(BaseModel):
    intensity: int
    persistence: int
    deviation: int
    population: int
    environmental: int
    infrastructure: int


class PipelineMeta(BaseModel):
    """Raw ml/pipeline.py output, preserved alongside the lossily-mapped
    fields above it — see module docstring."""

    thermalStatusRaw: str | None = None
    thermalTier: str | None = None
    thermalDetails: str | None = None
    classificationRaw: str | None = None
    classificationReliability: str | None = None
    riskLevelRaw: str | None = None
    riskBreakdown: dict[str, Any] | None = None


class ThermalEvent(BaseModel):
    id: str
    timestamp: str | None = None
    latitude: float
    longitude: float
    brightness: float | None = None
    confidence: float | None = None

    facilityId: str | None = None
    facilityName: str | None = None
    facilityType: str | None = None
    distanceToFacility: float | None = None

    classification: str
    classificationConfidence: float

    thermalStatus: ThermalStatus
    deviationScore: int
    riskScore: int
    riskLevel: RiskLevel
    lifecycle: LifecycleState
    detectionCount: int
    environmentalImpact: EnvironmentalImpact

    riskReasons: list[str] = Field(default_factory=list)
    deviationReasons: list[str] = Field(default_factory=list)
    riskComponents: RiskComponents

    pipelineMeta: PipelineMeta | None = None
