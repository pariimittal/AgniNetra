"""
backend/tests/test_mapping.py

Pure-logic tests for backend/services/mapping.py — no pandas/sklearn/
FastAPI/Pydantic dependency, so these should run in any environment that
merely has `pytest` installed.

Run: pytest backend/tests/test_mapping.py -v
"""

from __future__ import annotations

from backend.services import mapping


def test_classification_gas_flare_alias() -> None:
    """The trained model emits 'Gas Flare' (ml/merge_and_label.py), which
    must be canonicalized to the frontend's 'Gas Flare / Persistent Source'."""
    assert mapping.map_classification("Gas Flare") == "Gas Flare / Persistent Source"


def test_classification_known_values_pass_through() -> None:
    for label in [
        "Industrial Fire",
        "Wildfire",
        "Agricultural Burning",
        "Mining Activity",
        "Unknown",
        "Gas Flare / Persistent Source",
    ]:
        assert mapping.map_classification(label) == label


def test_classification_unknown_or_missing_falls_back() -> None:
    assert mapping.map_classification(None) == "Unknown"
    assert mapping.map_classification("") == "Unknown"
    assert mapping.map_classification("Something Nobody Trained On") == "Unknown"


def test_risk_level_low() -> None:
    assert mapping.map_risk_level(0) == "LOW"
    assert mapping.map_risk_level(39) == "LOW"


def test_risk_level_medium_maps_to_moderate() -> None:
    # ml/risk.py's "MEDIUM" band is score 40-69; frontend has no MEDIUM,
    # only MODERATE.
    assert mapping.map_risk_level(40) == "MODERATE"
    assert mapping.map_risk_level(55) == "MODERATE"
    assert mapping.map_risk_level(69) == "MODERATE"


def test_risk_level_high_and_critical_split() -> None:
    assert mapping.map_risk_level(70) == "HIGH"
    assert mapping.map_risk_level(84) == "HIGH"
    assert mapping.map_risk_level(85) == "CRITICAL"
    assert mapping.map_risk_level(100) == "CRITICAL"


def test_thermal_status_normal() -> None:
    assert mapping.map_thermal_status("Normal", "facility") == "NORMAL"
    assert mapping.map_thermal_status("Normal", "type") == "NORMAL"


def test_thermal_status_abnormal_facility_tier() -> None:
    assert mapping.map_thermal_status("Abnormal", "facility") == "ABNORMAL"


def test_thermal_status_abnormal_type_tier_is_milder() -> None:
    assert mapping.map_thermal_status("Abnormal", "type") == "MILDLY_ABNORMAL"


def test_thermal_status_insufficient_history_does_not_claim_abnormal() -> None:
    """Per fingerprint.py's own docstring warning, 'Insufficient History'
    must never be silently promoted to a claim of abnormality. We map it to
    NORMAL as the least-alarming safe default, not as a genuine finding —
    the raw status is preserved separately in pipelineMeta."""
    result = mapping.map_thermal_status("Insufficient History", "none")
    assert result == "NORMAL"
    assert result != "ABNORMAL"
    assert result != "MILDLY_ABNORMAL"


def test_environmental_impact_all_known_values() -> None:
    assert mapping.map_environmental_impact("Low") == "LOW"
    assert mapping.map_environmental_impact("Moderate") == "MODERATE"
    assert mapping.map_environmental_impact("High") == "HIGH"


def test_environmental_impact_severe_maps_to_high() -> None:
    assert mapping.map_environmental_impact("Severe") == "HIGH"


def test_environmental_impact_unknown_defaults_to_moderate() -> None:
    assert mapping.map_environmental_impact(None) == "MODERATE"
    assert mapping.map_environmental_impact("") == "MODERATE"
    assert mapping.map_environmental_impact("something-unexpected") == "MODERATE"


def test_risk_components_shape_and_range() -> None:
    breakdown = {
        "base_severity": 15,
        "thermal_intensity": 5.0,
        "persistence": 6.0,
        "abnormality_bonus": 10,
        "infrastructure_importance": 10.0,
        "environmental_sensitivity": 4.5,
        "confidence_adjustment": -0.4,
    }
    components = mapping.map_risk_components(breakdown)
    assert set(components.keys()) == {
        "intensity",
        "persistence",
        "deviation",
        "population",
        "environmental",
        "infrastructure",
    }
    for value in components.values():
        assert 0 <= value <= 100
    # population has no upstream signal by team decision (Phase 1 audit) —
    # must never be silently invented.
    assert components["population"] == 0


def test_risk_components_max_values_saturate_at_100() -> None:
    breakdown = {
        "thermal_intensity": 999,
        "persistence": 999,
        "abnormality_bonus": 999,
        "infrastructure_importance": 999,
        "environmental_sensitivity": 999,
    }
    components = mapping.map_risk_components(breakdown)
    for key in ("intensity", "persistence", "deviation", "environmental", "infrastructure"):
        assert components[key] == 100


def test_lifecycle_first_seen() -> None:
    assert mapping.map_lifecycle(persistence_score=0.05, n_detections_total=1) == "FIRST_SEEN"


def test_lifecycle_persistent() -> None:
    assert mapping.map_lifecycle(persistence_score=0.75, n_detections_total=20) == "PERSISTENT"


def test_lifecycle_default_growing() -> None:
    assert mapping.map_lifecycle(persistence_score=0.3, n_detections_total=5) == "GROWING"


def test_lifecycle_never_invents_declining_or_reignited() -> None:
    """No component tracks anomaly history over time, so these states must
    never be emitted — see mapping.py module docstring."""
    for persistence_score in (0.0, 0.1, 0.3, 0.5, 0.6, 0.9, 1.0):
        for n in (0, 1, 5, 30):
            result = mapping.map_lifecycle(persistence_score, n)
            assert result not in ("DECLINING", "REIGNITED", "RESOLVED")


def test_deviation_reasons_uses_triggered_by_when_present() -> None:
    fingerprint_result = {"triggered_by": ["brightness", "detections_30d"], "details": "irrelevant"}
    reasons = mapping.build_deviation_reasons(fingerprint_result)
    assert len(reasons) == 2
    assert all(isinstance(r, str) and r for r in reasons)


def test_deviation_reasons_falls_back_to_details() -> None:
    fingerprint_result = {"triggered_by": [], "details": "Insufficient history at any tier."}
    reasons = mapping.build_deviation_reasons(fingerprint_result)
    assert reasons == ["Insufficient history at any tier."]


def test_risk_reasons_never_empty() -> None:
    reasons = mapping.build_risk_reasons({"breakdown": {}}, classification="Unknown")
    assert len(reasons) >= 1
