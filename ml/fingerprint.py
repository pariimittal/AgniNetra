"""
fingerprint.py — AgniLens / Person 4 (Thermal Fingerprint + Risk Engine)

PURPOSE
-------
For every incoming thermal anomaly, answer: "Is this normal for what's here,
or is it behaving abnormally compared to its own history?"

Because we don't have a clean facility ID for every anomaly (real Singrauli
data has no stable facility name, and Person 2's mock stand-in gives every
row a UNIQUE Facility_N — meaning no two rows ever share a facility), we use
a TWO-TIER baseline lookup:

  Tier 1 — Facility-level baseline
      Group anomalies by an explicit facility identifier if one exists
      AND that group has >= MIN_SAMPLES_FACILITY points.
      This is the most precise baseline.

  Tier 2 — Type-level baseline (fallback)
      Group anomalies by (nearest_industry, land_cover) — e.g.
      "type:refinery|industrial" or "type:none|unknown" — when there isn't
      enough facility-specific history. This is coarser but still
      meaningful: "how do refineries in general behave?" instead of
      "how does THIS refinery behave?".

  Tier 3 — Insufficient History
      Fewer than MIN_SAMPLES_TYPE points even at the type level. We can't
      responsibly call anything abnormal yet, so we say so explicitly
      instead of guessing.

This tiering is intentional and should be reported to the frontend/backend
so nobody mistakes a Tier 2 "Abnormal" for the same confidence as a Tier 1
"Abnormal".

INPUT SCHEMA (per anomaly, matches Person 3's model input + a few extras)
---------------------------------------------------------------------
{
    "id": "ANM001",                 # optional but recommended
    "facility": "Singrauli STPS",   # optional — may be missing/None/"none"
    "brightness": 342.5,
    "confidence": 87,               # FIRMS detection confidence (0-100), NOT model confidence
    "detections_30d": 12,
    "persistence_score": 0.40,      # 0-1
    "n_detections_total": 40,
    "distance_m": 420,
    "nearest_forest_km": 3.2,       # may be None/blank
    "nearest_industry": "refinery", # may be "none"
    "land_cover": "industrial",     # may be "unknown"
}

OUTPUT SCHEMA
-------------
{
    "thermal_status": "Abnormal" | "Normal" | "Insufficient History",
    "tier": "facility" | "type" | "none",
    "baseline_group": "Singrauli STPS" | "type:refinery|industrial" | None,
    "sample_size": 4,
    "triggered_by": ["brightness", "detections_30d"],   # empty if Normal
    "details": "human-readable explanation for the dashboard"
}
"""

from __future__ import annotations
from collections import defaultdict
from statistics import mean, pstdev
from typing import Optional

# ---------------------------------------------------------------------------
# Tunable constants — documented here so risk.py and the backend can trust
# the same numbers instead of guessing.
# ---------------------------------------------------------------------------
MIN_SAMPLES_FACILITY = 3     # min anomalies sharing a facility to trust a facility baseline
MIN_SAMPLES_TYPE = 3         # min anomalies sharing a type bucket to trust a type baseline
ABNORMAL_Z_THRESHOLD = 1.5   # how many std-devs above the mean counts as "abnormal"
ZERO_STD_MARGIN = 0.25       # if std==0 (identical history), flag if current exceeds mean by 25%+

# Metrics we compare current behaviour against baseline for.
COMPARE_METRICS = ["brightness", "detections_30d", "persistence_score"]


def _safe_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _facility_key(anomaly: dict) -> Optional[str]:
    facility = anomaly.get("facility")
    if not facility or str(facility).strip().lower() in ("", "none", "unknown", "n/a"):
        return None
    return str(facility).strip()


def _type_key(anomaly: dict) -> str:
    # nearest_industry / land_cover are far more likely to be populated
    # than a clean facility name, so this bucket is the reliable fallback.
    industry = (anomaly.get("nearest_industry") or "none").strip().lower()
    land_cover = (anomaly.get("land_cover") or "unknown").strip().lower()
    return f"type:{industry}|{land_cover}"


def build_baseline(historical_data: list[dict]) -> dict:
    """
    Build both facility-level and type-level baselines from a list of
    historical anomaly dicts (same schema as a single anomaly above).

    Returns:
    {
        "facility": {facility_name: {"brightness": (mean, std), ...,
                                       "n": count}},
        "type":     {type_key:       {"brightness": (mean, std), ...,
                                       "n": count}},
    }
    """
    facility_groups = defaultdict(list)
    type_groups = defaultdict(list)

    for row in historical_data:
        fkey = _facility_key(row)
        if fkey:
            facility_groups[fkey].append(row)
        type_groups[_type_key(row)].append(row)

    def summarize(groups: dict) -> dict:
        summary = {}
        for key, rows in groups.items():
            stats = {"n": len(rows)}
            for metric in COMPARE_METRICS:
                values = [_safe_float(r.get(metric)) for r in rows]
                values = [v for v in values if v is not None]
                if values:
                    stats[metric] = (mean(values), pstdev(values) if len(values) > 1 else 0.0) # pyright: ignore[reportArgumentType]
                else:
                    stats[metric] = (None, None) # pyright: ignore[reportArgumentType]
            summary[key] = stats
        return summary

    return {
        "facility": summarize(facility_groups),
        "type": summarize(type_groups),
    }


def get_fingerprint(anomaly: dict, baseline: dict) -> dict:
    """
    Compare a single anomaly against the baseline, using Tier 1 (facility)
    first, falling back to Tier 2 (type), falling back to Tier 3
    (insufficient history).
    """
    fkey = _facility_key(anomaly)
    tkey = _type_key(anomaly)

    tier = None
    group_key = None
    stats = None

    if fkey and fkey in baseline["facility"] and baseline["facility"][fkey]["n"] >= MIN_SAMPLES_FACILITY:
        tier = "facility"
        group_key = fkey
        stats = baseline["facility"][fkey]
    elif tkey in baseline["type"] and baseline["type"][tkey]["n"] >= MIN_SAMPLES_TYPE:
        tier = "type"
        group_key = tkey
        stats = baseline["type"][tkey]

    if not tier:
        return {
            "thermal_status": "Insufficient History",
            "tier": "none",
            "baseline_group": None,
            "sample_size": 0,
            "triggered_by": [],
            "details": (
                "Not enough historical data at either the facility or type level "
                "to establish a baseline yet. Treat this anomaly's abnormality as unknown, "
                "not as 'Normal'."
            ),
        }

    triggered = []
    for metric in COMPARE_METRICS:
        current_val = _safe_float(anomaly.get(metric))
        base_mean, base_std = stats.get(metric, (None, None)) # pyright: ignore[reportOptionalMemberAccess]
        if current_val is None or base_mean is None:
            continue
        if base_std and base_std > 0:
            z = (current_val - base_mean) / base_std
            if z >= ABNORMAL_Z_THRESHOLD:
                triggered.append(metric)
        else:
            # Identical historical values (std == 0) — use a simple relative margin
            if base_mean > 0 and current_val >= base_mean * (1 + ZERO_STD_MARGIN):
                triggered.append(metric)

    status = "Abnormal" if triggered else "Normal"
    tier_label = "facility-specific" if tier == "facility" else "type-level (same category)"

    details = (
        f"Compared against {stats['n']} historical points using a {tier_label} baseline" # pyright: ignore[reportOptionalSubscript]
        f" ('{group_key}')."
    )
    if triggered:
        details += f" Elevated relative to baseline on: {', '.join(triggered)}."
    else:
        details += " All monitored metrics are within normal range."

    return {
        "thermal_status": status,
        "tier": tier,
        "baseline_group": group_key,
        "sample_size": stats["n"], # pyright: ignore[reportOptionalSubscript]
        "triggered_by": triggered,
        "details": details,
    }


if __name__ == "__main__":
    # ---- Sanity checks -----------------------------------------------
    # Mock history: 4 real-shaped Singrauli-style points, no facility name,
    # same type bucket (type:none|unknown) — mirrors what Person 1/2 actually
    # observed tonight (4 real detections, no OSM match yet).
    history = [
        {"brightness": 320, "detections_30d": 3, "persistence_score": 0.2,
         "nearest_industry": "none", "land_cover": "unknown"},
        {"brightness": 330, "detections_30d": 4, "persistence_score": 0.25,
         "nearest_industry": "none", "land_cover": "unknown"},
        {"brightness": 315, "detections_30d": 3, "persistence_score": 0.22,
         "nearest_industry": "none", "land_cover": "unknown"},
        {"brightness": 400, "detections_30d": 14, "persistence_score": 0.6,
         "nearest_industry": "none", "land_cover": "unknown"},  # the spike
    ]
    baseline = build_baseline(history)

    spike_point = history[3]
    result = get_fingerprint(spike_point, baseline)
    print("Spike point fingerprint:", result)
    assert result["thermal_status"] == "Abnormal", "Expected the spike point to be flagged abnormal"
    assert result["tier"] == "type", "Expected fallback to type-level tier (no facility names present)"

    calm_point = history[0]
    result2 = get_fingerprint(calm_point, baseline)
    print("Calm point fingerprint:", result2)

    # Edge case: brand-new anomaly type never seen before
    novel = {"brightness": 500, "detections_30d": 20, "persistence_score": 0.9,
              "nearest_industry": "quarry", "land_cover": "mining"}
    result3 = get_fingerprint(novel, baseline)
    print("Novel-type fingerprint:", result3)
    assert result3["thermal_status"] == "Insufficient History"

    print("\nAll fingerprint.py sanity checks passed.")
