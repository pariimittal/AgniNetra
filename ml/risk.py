"""
risk.py — AgniLens / Person 4 (Thermal Fingerprint + Risk Engine)

Combines:
  1. Raw anomaly fields (brightness, distance_m, nearest_forest_km, etc.)
  2. Person 3's classification output ({"classification": ..., "confidence": ...})
  3. This module's own fingerprint output (from fingerprint.py)

...into a single explainable risk score.

IMPORTANT DESIGN NOTE — read this before changing weights
-----------------------------------------------------------
Person 3 flagged that Gas Flare and Mining Activity are undertrained right
now (Gas Flare has had as few as 1 training example) and their MODEL
CONFIDENCE will be artificially low, independent of actual risk. If we
naively multiply risk_score by model confidence, those two classes would
always look "safe" — which would be actively wrong and dangerous in a demo.

So this engine does NOT multiply the whole risk score by raw model
confidence. Instead:
  - Each class has a fixed BASE_SEVERITY (what that class typically means
    for risk), independent of how confident the model was.
  - Model confidence only nudges the score within a small capped range
    (CONFIDENCE_ADJUSTMENT_CAP), so an uncertain classification can't
    tank or inflate the score dramatically.
  - We separately expose a `classification_reliability` field so the
    frontend can show "Low confidence — limited training data" without
    that showing up as "this is low risk."

`population_proximity` is NOT used anywhere below — Person 2 confirmed
it's permanently removed from the schema (always returned "unknown").
If it's reintroduced later, it should become a proximity multiplier here.

INPUT
-----
anomaly: raw dict, e.g.
    {
        "brightness": 342.5,
        "persistence_score": 0.40,
        "distance_m": 420,
        "nearest_forest_km": 3.2,       # may be None
        "nearest_industry": "refinery", # may be "none"
        "land_cover": "industrial",     # may be "unknown"
    }
classification: {"classification": "Industrial Fire", "confidence": 0.91}
fingerprint: output of fingerprint.get_fingerprint(...)

OUTPUT
------
{
    "risk_score": 87,             # 0-100 int
    "risk_level": "HIGH",         # HIGH / MEDIUM / LOW
    "environmental_impact": "Moderate",  # Severe / High / Moderate / Low
    "classification_reliability": "High" | "Low - limited training data",
    "breakdown": {                # for the dashboard's "why" panel
        "thermal_intensity": 22.0,
        "persistence": 16.0,
        "abnormality_bonus": 15.0,
        "infrastructure_importance": 20.0,
        "environmental_sensitivity": 10.0,
        "confidence_adjustment": 4.0,
    }
}
"""

from __future__ import annotations
from typing import Optional

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Base severity per class (0-40 points), independent of model confidence.
# Reflects "if this classification is correct, how concerning is it by default".
BASE_SEVERITY = {
    "Industrial Fire": 35,
    "Gas Flare / Persistent Source": 30,
    "Mining Activity": 22,
    "Wildfire": 25,
    "Agricultural Burning": 12,
    "Unknown": 15,
}

# Classes Person 3 flagged as undertrained tonight. Their low model
# confidence should NOT be read as low risk.
LOW_TRAINING_DATA_CLASSES = {"Gas Flare / Persistent Source", "Mining Activity"}

# How much model confidence can move the score, at most (points, not %).
CONFIDENCE_ADJUSTMENT_CAP = 5

# Infrastructure importance by facility type (0-25 points).
INFRASTRUCTURE_IMPORTANCE = {
    "power plant": 25,
    "refinery": 25,
    "mine": 15,
    "factory": 15,
    "quarry": 12,
    "none": 0,
}
DEFAULT_INFRASTRUCTURE_IMPORTANCE = 8  # unrecognized-but-present facility type

# Proximity to industry: closer = more likely this IS the facility's fire,
# which raises confidence that infrastructure is genuinely involved.
PROXIMITY_FULL_CREDIT_M = 500      # at or under this distance, full credit
PROXIMITY_ZERO_CREDIT_M = 5000     # at or beyond this distance, no credit
MAX_PROXIMITY_POINTS = 10

MAX_ENV_SENSITIVITY_POINTS = 15
FOREST_FULL_SENSITIVITY_KM = 1.0   # forest within 1km = max sensitivity
FOREST_ZERO_SENSITIVITY_KM = 15.0  # forest 15km+ away = no added sensitivity

RISK_LEVEL_THRESHOLDS = {"HIGH": 70, "MEDIUM": 40}  # >=70 HIGH, >=40 MEDIUM, else LOW


def _safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, low, high):
    return max(low, min(high, value))


def _linear_credit(value: float, full_at: float, zero_at: float, max_points: float) -> float:
    """
    Linearly scale `value` between full credit (at/under `full_at`) and
    zero credit (at/over `zero_at`). Handles both "closer is worse"
    (full_at < zero_at, e.g. distance) shapes.
    """
    if value <= full_at:
        return max_points
    if value >= zero_at:
        return 0.0
    fraction = 1 - (value - full_at) / (zero_at - full_at)
    return max_points * fraction


def _infrastructure_score(nearest_industry: Optional[str]) -> float:
    if not nearest_industry:
        return 0.0
    key = nearest_industry.strip().lower()
    if key == "none":
        return 0.0
    return INFRASTRUCTURE_IMPORTANCE.get(key, DEFAULT_INFRASTRUCTURE_IMPORTANCE)


def _environmental_sensitivity_score(nearest_forest_km) -> float:
    forest_km = _safe_float(nearest_forest_km, default=None) # pyright: ignore[reportArgumentType]
    if forest_km is None:
        # Unknown forest distance — assume moderate-low sensitivity rather
        # than zero, so we don't silently under-count environmental risk
        # just because the field is missing.
        return MAX_ENV_SENSITIVITY_POINTS * 0.3
    return _linear_credit(forest_km, FOREST_FULL_SENSITIVITY_KM, FOREST_ZERO_SENSITIVITY_KM,
                           MAX_ENV_SENSITIVITY_POINTS)


def _environmental_impact_label(classification: str, nearest_forest_km, land_cover: Optional[str]) -> str:
    forest_km = _safe_float(nearest_forest_km, default=None) # pyright: ignore[reportArgumentType]
    land_cover = (land_cover or "unknown").strip().lower()

    near_forest = forest_km is not None and forest_km <= 2.0

    if classification == "Wildfire" and near_forest:
        return "Severe"
    if classification == "Industrial Fire" and near_forest:
        return "High"
    if classification in ("Industrial Fire", "Gas Flare / Persistent Source"):
        return "Moderate" if land_cover == "industrial" else "High"
    if classification == "Wildfire":
        return "Moderate"
    if classification == "Mining Activity":
        return "Moderate"
    if classification == "Agricultural Burning":
        return "Low" if not near_forest else "Moderate"
    return "Moderate"  # Unknown class — don't understate it


def compute_risk(anomaly: dict, classification: dict, fingerprint: dict) -> dict:
    cls_name = classification.get("classification", "Unknown")
    model_confidence = _clamp(_safe_float(classification.get("confidence"), 0.5), 0.0, 1.0)

    # --- Component scores -------------------------------------------------
    base_severity = BASE_SEVERITY.get(cls_name, BASE_SEVERITY["Unknown"])

    thermal_intensity = _clamp((_safe_float(anomaly.get("brightness"), 300) - 300) / 3, 0, 25)
    persistence = _clamp(_safe_float(anomaly.get("persistence_score"), 0) * 20, 0, 20)

    fingerprint_status = fingerprint.get("thermal_status", "Insufficient History")
    fingerprint_tier = fingerprint.get("tier", "none")
    if fingerprint_status == "Abnormal":
        # Trust a facility-level abnormality more than a type-level one.
        abnormality_bonus = 15 if fingerprint_tier == "facility" else 10
    elif fingerprint_status == "Insufficient History":
        abnormality_bonus = 0
    else:
        abnormality_bonus = 0

    infrastructure_importance = _infrastructure_score(anomaly.get("nearest_industry"))
    # Discount infrastructure importance by proximity — a refinery 4km away
    # is much less likely to be the actual source than one 400m away.
    proximity_credit = _linear_credit(
        _safe_float(anomaly.get("distance_m"), PROXIMITY_ZERO_CREDIT_M),
        PROXIMITY_FULL_CREDIT_M, PROXIMITY_ZERO_CREDIT_M, 1.0,
    )
    infrastructure_importance = infrastructure_importance * (0.4 + 0.6 * proximity_credit)

    environmental_sensitivity = _environmental_sensitivity_score(anomaly.get("nearest_forest_km"))

    # Confidence adjustment: small, capped, and DOES NOT apply the same way
    # to undertrained classes (see module docstring).
    if cls_name in LOW_TRAINING_DATA_CLASSES:
        # Don't reward or punish based on confidence for classes we know
        # are undertrained — apply half the normal adjustment range so a
        # shaky "0.3 confidence Gas Flare" isn't scored as if it's fine.
        confidence_adjustment = (model_confidence - 0.5) * (CONFIDENCE_ADJUSTMENT_CAP * 0.5)
    else:
        confidence_adjustment = (model_confidence - 0.5) * CONFIDENCE_ADJUSTMENT_CAP

    raw_score = (
        base_severity
        + thermal_intensity * 0.4
        + persistence * 0.6
        + abnormality_bonus
        + infrastructure_importance * 0.8
        + environmental_sensitivity * 0.6
        + confidence_adjustment
    )
    risk_score = int(round(_clamp(raw_score, 0, 100)))

    if risk_score >= RISK_LEVEL_THRESHOLDS["HIGH"]:
        risk_level = "HIGH"
    elif risk_score >= RISK_LEVEL_THRESHOLDS["MEDIUM"]:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    reliability = (
        "Low - limited training data" if cls_name in LOW_TRAINING_DATA_CLASSES else "High"
    )

    environmental_impact = _environmental_impact_label(
        cls_name, anomaly.get("nearest_forest_km"), anomaly.get("land_cover")
    )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "environmental_impact": environmental_impact,
        "classification_reliability": reliability,
        "breakdown": {
            "base_severity": round(base_severity, 1),
            "thermal_intensity": round(thermal_intensity * 0.4, 1),
            "persistence": round(persistence * 0.6, 1),
            "abnormality_bonus": round(abnormality_bonus, 1),
            "infrastructure_importance": round(infrastructure_importance * 0.8, 1),
            "environmental_sensitivity": round(environmental_sensitivity * 0.6, 1),
            "confidence_adjustment": round(confidence_adjustment, 1),
        },
    }


if __name__ == "__main__":
    # ---- Sanity checks matching the schema in the master doc ----------
    anomaly_high = {
        "brightness": 342.5, "persistence_score": 0.40,
        "distance_m": 420, "nearest_forest_km": 3.2,
        "nearest_industry": "refinery", "land_cover": "industrial",
    }
    classification_high = {"classification": "Industrial Fire", "confidence": 0.91}
    fingerprint_high = {"thermal_status": "Abnormal", "tier": "facility"}

    result = compute_risk(anomaly_high, classification_high, fingerprint_high)
    print("High-risk example:", result)
    assert result["risk_level"] == "HIGH"
    assert result["classification_reliability"] == "High"

    # Undertrained class with low model confidence — must NOT read as low risk
    anomaly_flare = {
        "brightness": 360, "persistence_score": 0.7,
        "distance_m": 200, "nearest_forest_km": None,
        "nearest_industry": "refinery", "land_cover": "industrial",
    }
    classification_flare = {"classification": "Gas Flare / Persistent Source", "confidence": 0.32}
    fingerprint_flare = {"thermal_status": "Normal", "tier": "type"}
    result2 = compute_risk(anomaly_flare, classification_flare, fingerprint_flare)
    print("Low-confidence Gas Flare example:", result2)
    assert result2["classification_reliability"] == "Low - limited training data"
    assert result2["risk_level"] in ("MEDIUM", "HIGH"), (
        "Low model confidence on an undertrained class should not collapse risk to LOW"
    )

    # Edge case: nearest_industry == "none", nearest_forest_km missing entirely
    anomaly_edge = {
        "brightness": 305, "persistence_score": 0.1,
        "distance_m": None, "nearest_forest_km": None,
        "nearest_industry": "none", "land_cover": "unknown",
    }
    classification_edge = {"classification": "Unknown", "confidence": 0.4}
    fingerprint_edge = {"thermal_status": "Insufficient History", "tier": "none"}
    result3 = compute_risk(anomaly_edge, classification_edge, fingerprint_edge)
    print("Sparse/edge-case example:", result3)
    assert result3["risk_level"] == "LOW"

    print("\nAll risk.py sanity checks passed.")