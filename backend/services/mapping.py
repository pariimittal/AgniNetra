"""
backend/services/mapping.py

Converts ml/pipeline.py's `process_anomaly()` output (and the raw merged
FIRMS+geospatial row it was computed from) into the frontend's ThermalEvent
shape (src/types/index.ts).

WHY THIS MODULE EXISTS
-----------------------
Phase 1 audit found that the ML/risk/fingerprint components and the
frontend use DIFFERENT VOCABULARIES for several fields (sections E2-E5).
None of the mismatches are bugs in ml/ — they're independent teams'
components that were never reconciled. This module is that reconciliation
layer, kept isolated so:
  - it's obvious exactly which values are "real" pipeline output vs.
    "derived/approximated for display", and
  - a future change to the frontend's types or the ML output only requires
    editing this one file.

KNOWN LOSSY / APPROXIMATE MAPPINGS (read before trusting a field blindly)
--------------------------------------------------------------------------
- classification: ml/merge_and_label.py trained the model on the label
  string "Gas Flare" (not "Gas Flare / Persistent Source", which is what
  ml/risk.py's BASE_SEVERITY dict and the frontend's ClassificationType
  both expect — Phase 1 audit E2). We canonicalize known legacy/variant
  labels here. Any classification string that still doesn't match the
  frontend's known ClassificationType values is mapped to "Unknown" rather
  than passed through as a broken/unrecognized value.

- riskLevel: ml/risk.py only emits HIGH/MEDIUM/LOW. The frontend has a 4th
  tier, CRITICAL. We split risk.py's own HIGH band (score >= 70) at score
  >= 85 to produce CRITICAL, using risk.py's own numeric risk_score — no
  new scoring logic, just a finer-grained label on top of an existing
  number.

- thermalStatus: fingerprint.py emits "Abnormal" / "Normal" /
  "Insufficient History" (3 values, tiered by confidence: facility vs type
  vs none). The frontend's ThermalStatus has 3 different values (NORMAL /
  MILDLY_ABNORMAL / ABNORMAL) with no direct equivalent for "insufficient
  history". We map "Abnormal" at the coarser type-level tier down to
  MILDLY_ABNORMAL (since it's a lower-confidence signal than a
  facility-level baseline), and "Insufficient History" to NORMAL as the
  least-alarming safe default — NOT because it durably means normal.
  fingerprint.py's own docstring explicitly warns "treat this anomaly's
  abnormality as unknown, not as 'Normal'"; the full raw status/tier/detail
  string is preserved in the response's `pipelineMeta` block for anyone
  who needs the real answer instead of the lossy 3-way label.

- environmentalImpact: risk.py's 4-value scale (Severe/High/Moderate/Low)
  collapses onto the frontend's 3-value scale (LOW/MODERATE/HIGH) by
  merging Severe into HIGH.

- riskComponents (intensity/persistence/deviation/population/environmental/
  infrastructure): the frontend renders each of these as an independent
  0-100 progress bar (see src/App.tsx RiskBars — `width: ${value}%`).
  risk.py's `breakdown` dict instead reports WEIGHTED POINT CONTRIBUTIONS
  toward a single 0-100 risk_score (e.g. thermal_intensity caps at 10
  points, not 100). We rescale each weighted contribution back to a 0-100
  scale using risk.py's own documented maximums (see _RISK_COMPONENT_MAX
  below) so the bars are visually meaningful, rather than showing a
  thermal_intensity bar that can never exceed ~10% even at maximum
  brightness. `population` is always 0, clearly not a measured value —
  geospatial/config.py's INCLUDE_POPULATION_PROXIMITY is False by explicit
  team decision (Phase 1 audit), so no population signal exists anywhere
  upstream to report.

- deviationScore (top-level): no upstream component computes a numeric
  deviation score. We reuse the same rescaled `deviation` value we compute
  for riskComponents.deviation (derived from fingerprint.py's abnormality
  bonus) so there's exactly one, internally-consistent, clearly-sourced
  number, instead of two independently-invented ones.

- lifecycle: NOBODY on the team currently computes this (confirmed absent
  from ml/, geospatial/, and firms_pipeline.py in the Phase 1 audit) — it
  would require comparing an anomaly against its own prior snapshots over
  time, which no component does. We derive a coarse, clearly-labeled
  placeholder from persistence_score/n_detections_total alone (the only
  real signals available) and never emit DECLINING/REIGNITED/RESOLVED,
  since nothing justifies those without real temporal tracking.

- detectionCount: mapped from `detections_30d` (the trailing-window count),
  not `n_detections_total` (all-time) — closer to what a dashboard
  "recent activity" metric usually means.

None of this fabricates raw satellite data (brightness, confidence,
coordinates, timestamps all pass through from the real merged
FIRMS+geospatial row) — it only translates already-computed, real pipeline
outputs into the frontend's vocabulary.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

_KNOWN_CLASSIFICATIONS = {
    "Industrial Fire",
    "Gas Flare / Persistent Source",
    "Wildfire",
    "Agricultural Burning",
    "Mining Activity",
    "Unknown",
}

# Legacy/variant labels seen in the actual trained model's output
# (ml/merge_and_label.py's label_row(), Phase 1 audit section E2) mapped to
# the frontend's canonical ClassificationType strings.
_CLASSIFICATION_ALIASES = {
    "Gas Flare": "Gas Flare / Persistent Source",
}


def map_classification(raw_classification: str | None) -> str:
    if not raw_classification:
        return "Unknown"
    canonical = _CLASSIFICATION_ALIASES.get(raw_classification, raw_classification)
    if canonical in _KNOWN_CLASSIFICATIONS:
        return canonical
    return "Unknown"


# ---------------------------------------------------------------------------
# risk level (HIGH/MEDIUM/LOW -> LOW/MODERATE/HIGH/CRITICAL)
# ---------------------------------------------------------------------------

# Matches ml/risk.py's own RISK_LEVEL_THRESHOLDS = {"HIGH": 70, "MEDIUM": 40}.
# CRITICAL is a NEW split within risk.py's HIGH band, using its own
# risk_score number — not a new scoring rule.
_CRITICAL_THRESHOLD = 85


def map_risk_level(risk_score: int) -> str:
    if risk_score >= _CRITICAL_THRESHOLD:
        return "CRITICAL"
    if risk_score >= 70:
        return "HIGH"
    if risk_score >= 40:
        return "MODERATE"
    return "LOW"


# ---------------------------------------------------------------------------
# thermal status (Abnormal/Normal/Insufficient History -> NORMAL/MILDLY_ABNORMAL/ABNORMAL)
# ---------------------------------------------------------------------------


def map_thermal_status(raw_status: str, tier: str) -> str:
    if raw_status == "Abnormal":
        return "ABNORMAL" if tier == "facility" else "MILDLY_ABNORMAL"
    # "Normal" and "Insufficient History" both land on NORMAL — see the
    # module docstring for why this is a known lossy simplification.
    return "NORMAL"


# ---------------------------------------------------------------------------
# environmental impact (Severe/High/Moderate/Low -> LOW/MODERATE/HIGH)
# ---------------------------------------------------------------------------

_ENVIRONMENTAL_IMPACT_MAP = {
    "severe": "HIGH",
    "high": "HIGH",
    "moderate": "MODERATE",
    "low": "LOW",
}


def map_environmental_impact(raw_impact: str | None) -> str:
    return _ENVIRONMENTAL_IMPACT_MAP.get((raw_impact or "").strip().lower(), "MODERATE")


# ---------------------------------------------------------------------------
# risk components (weighted point contributions -> independent 0-100 bars)
# ---------------------------------------------------------------------------

# Maximum possible weighted contribution for each ml/risk.py breakdown key,
# derived from that module's own documented constants (not re-derived
# empirically): thermal_intensity <= 25*0.4, persistence <= 20*0.6,
# abnormality_bonus <= 15, infrastructure_importance <= 25*0.8,
# environmental_sensitivity <= 15*0.6.
_RISK_COMPONENT_MAX = {
    "thermal_intensity": 25 * 0.4,
    "persistence": 20 * 0.6,
    "abnormality_bonus": 15.0,
    "infrastructure_importance": 25 * 0.8,
    "environmental_sensitivity": 15 * 0.6,
}


def _rescale_to_percent(value: float, max_value: float) -> int:
    if max_value <= 0:
        return 0
    pct = (value / max_value) * 100.0
    return int(round(max(0.0, min(100.0, pct))))


def map_risk_components(risk_breakdown: dict[str, Any]) -> dict[str, int]:
    """
    Returns the frontend's 6-key riskComponents shape, each rescaled to an
    independent 0-100 range. `population` is always 0 — see module
    docstring (no population signal exists upstream by team decision).
    """
    return {
        "intensity": _rescale_to_percent(
            risk_breakdown.get("thermal_intensity", 0.0), _RISK_COMPONENT_MAX["thermal_intensity"]
        ),
        "persistence": _rescale_to_percent(
            risk_breakdown.get("persistence", 0.0), _RISK_COMPONENT_MAX["persistence"]
        ),
        "deviation": _rescale_to_percent(
            risk_breakdown.get("abnormality_bonus", 0.0), _RISK_COMPONENT_MAX["abnormality_bonus"]
        ),
        "population": 0,
        "environmental": _rescale_to_percent(
            risk_breakdown.get("environmental_sensitivity", 0.0),
            _RISK_COMPONENT_MAX["environmental_sensitivity"],
        ),
        "infrastructure": _rescale_to_percent(
            risk_breakdown.get("infrastructure_importance", 0.0),
            _RISK_COMPONENT_MAX["infrastructure_importance"],
        ),
    }


# ---------------------------------------------------------------------------
# lifecycle (coarse placeholder — see module docstring)
# ---------------------------------------------------------------------------


def map_lifecycle(persistence_score: float | None, n_detections_total: int | None) -> str:
    persistence_score = persistence_score or 0.0
    n_detections_total = n_detections_total or 0

    if persistence_score < 0.15 and n_detections_total <= 2:
        return "FIRST_SEEN"
    if persistence_score >= 0.6:
        return "PERSISTENT"
    return "GROWING"


# ---------------------------------------------------------------------------
# reasons (built from real pipeline output — fingerprint details/triggers,
# risk breakdown — not invented)
# ---------------------------------------------------------------------------

_TRIGGER_LABELS = {
    "brightness": "Brightness elevated relative to baseline",
    "detections_30d": "Detection frequency elevated relative to baseline",
    "persistence_score": "Persistence elevated relative to baseline",
}


def build_deviation_reasons(fingerprint_result: dict[str, Any]) -> list[str]:
    triggered = fingerprint_result.get("triggered_by") or []
    reasons = [_TRIGGER_LABELS.get(key, f"{key} elevated relative to baseline") for key in triggered]
    if not reasons:
        # Fall back to fingerprint.py's own human-readable explanation
        # (e.g. "Insufficient History" or "within normal range") rather
        # than showing an empty list.
        details = fingerprint_result.get("details")
        if details:
            reasons = [details]
    return reasons


def build_risk_reasons(risk_result: dict[str, Any], classification: str) -> list[str]:
    reasons: list[str] = []
    breakdown = risk_result.get("breakdown", {})

    if breakdown.get("base_severity", 0) >= 25:
        reasons.append(f"Classified as {classification}, a high base-severity category")
    if breakdown.get("infrastructure_importance", 0) >= 10:
        reasons.append("Located near significant industrial infrastructure")
    if breakdown.get("abnormality_bonus", 0) > 0:
        reasons.append("Thermal fingerprint flagged as abnormal vs. historical baseline")
    if breakdown.get("environmental_sensitivity", 0) >= 6:
        reasons.append("Near environmentally sensitive land cover (e.g. forest)")
    if risk_result.get("classification_reliability", "").startswith("Low"):
        reasons.append("Classification confidence is limited by training-data volume")

    if not reasons:
        reasons.append("No significant risk drivers identified")
    return reasons
