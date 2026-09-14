"""
pipeline.py — AgniLens / Person 4

Single entry point for Person 5 (Backend). Wires together:
    Person 3's classify_anomaly()  ->  fingerprint.get_fingerprint()  ->  risk.compute_risk()

and returns the exact final JSON shape from the team's frozen schema:

{
    "id": "ANM001",
    "lat": 28.6139,
    "lon": 77.2090,
    "source": "NASA FIRMS",
    "classification": "Industrial Fire",
    "confidence": 91,
    "thermal_status": "Abnormal",
    "risk_score": 87,
    "risk_level": "High",
    "persistence": 82,
    "environmental_impact": "Moderate",
    "facility": "Thermal Power Plant"
}

USAGE (backend side)
---------------------
    from pipeline import process_anomaly, build_baseline_from_history

    baseline = build_baseline_from_history(all_historical_anomalies)  # do this once, cache it
    result = process_anomaly(anomaly_dict, baseline)                  # per anomaly / per request

If Person 3's real model.py isn't importable in your environment yet, this
file falls back to a stub classifier so the rest of the pipeline is still
testable end to end — swap MODEL_AVAILABLE logic out once model.py is on
the path.
"""

from __future__ import annotations

import fingerprint
import risk # pyright: ignore[reportMissingImports]

try:
    from model import classify_anomaly  # pyright: ignore[reportAssignmentType] # Person 3's module
    MODEL_AVAILABLE = True
except ImportError:
    MODEL_AVAILABLE = False

    def classify_anomaly(features: dict) -> dict:
        """Stub used only if Person 3's model.py isn't on the path yet."""
        return {"classification": "Unknown", "confidence": 0.5}


def build_baseline_from_history(historical_anomalies: list[dict]) -> dict:
    """Thin wrapper so backend code only needs to import from this one file."""
    return fingerprint.build_baseline(historical_anomalies)


def process_anomaly(anomaly: dict, baseline: dict) -> dict:
    """
    anomaly: raw dict with at least the fields fingerprint.py / model.py expect
              (brightness, confidence, detections_30d, persistence_score,
               n_detections_total, distance_m, nearest_forest_km,
               nearest_industry, land_cover), plus id/lat/lon/facility/source
              for the final response shape.
    baseline: output of build_baseline_from_history(), built once and cached.
    """
    classification_input = {
        k: anomaly.get(k) for k in (
            "brightness", "confidence", "detections_30d", "persistence_score",
            "n_detections_total", "distance_m", "nearest_forest_km",
            "nearest_industry", "land_cover",
        )
    }
    classification_result = classify_anomaly(classification_input)
    fingerprint_result = fingerprint.get_fingerprint(anomaly, baseline)
    risk_result = risk.compute_risk(anomaly, classification_result, fingerprint_result)

    return {
        "id": anomaly.get("id"),
        "lat": anomaly.get("lat"),
        "lon": anomaly.get("lon"),
        "source": anomaly.get("source", "NASA FIRMS"),
        "classification": classification_result["classification"],
        "confidence": round(classification_result["confidence"] * 100, 1),
        "classification_reliability": risk_result["classification_reliability"],
        "thermal_status": fingerprint_result["thermal_status"],
        "thermal_tier": fingerprint_result["tier"],
        "thermal_details": fingerprint_result["details"],
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_result["risk_level"],
        "risk_breakdown": risk_result["breakdown"],
        "persistence": round(_pct(anomaly.get("persistence_score")), 1),
        "environmental_impact": risk_result["environmental_impact"],
        "facility": anomaly.get("facility"),
    }


def _pct(value):
    try:
        return float(value) * 100 if value is not None and float(value) <= 1 else float(value or 0)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    print(f"model.py importable: {MODEL_AVAILABLE} (stub classifier used if False)\n")

    history = [
        {"brightness": 320, "detections_30d": 3, "persistence_score": 0.2,
         "nearest_industry": "none", "land_cover": "unknown"},
        {"brightness": 330, "detections_30d": 4, "persistence_score": 0.25,
         "nearest_industry": "none", "land_cover": "unknown"},
        {"brightness": 315, "detections_30d": 3, "persistence_score": 0.22,
         "nearest_industry": "none", "land_cover": "unknown"},
    ]
    baseline = build_baseline_from_history(history)

    test_anomaly = {
        "id": "ANM001", "lat": 24.0983, "lon": 82.6746, "source": "NASA FIRMS",
        "facility": None, "brightness": 342.5, "confidence": 87,
        "detections_30d": 12, "persistence_score": 0.40, "n_detections_total": 40,
        "distance_m": 420, "nearest_forest_km": 3.2,
        "nearest_industry": "refinery", "land_cover": "industrial",
    }

    final = process_anomaly(test_anomaly, baseline)
    import json
    print(json.dumps(final, indent=2))