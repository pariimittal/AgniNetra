"""
backend/services/facility_service.py

Derives the frontend's `Facility` / `FacilityHistory` / `FingerprintData`
shapes (src/types/index.ts) from data that GENUINELY EXISTS in this
repository — there is no separate facility database anywhere (Phase 1
audit finding: the geospatial module only produces per-anomaly
"nearest-facility" features, not a facility registry with its own
identity/history). This module is the one place that gap is bridged, and
every approximation it makes is documented below.

REUSE, NOT DUPLICATION
-----------------------
This module does NOT re-run FIRMS/geospatial loading or the ML pipeline —
it consumes `backend.services.event_service.get_annotated_events()` (the
same raw rows + ml/pipeline.py outputs + mapped ThermalEvents already
computed once for GET /api/events) and `event_service.get_baseline()` (the
same ml/fingerprint.py baseline dict). Per the Phase 4 instructions, ML
processing lives in exactly one place (event_service); this module only
aggregates its output by facility.

WHERE A "FACILITY" COMES FROM
-------------------------------
Every anomaly row that has `nearest_industry != "none"` carries a
`nearest_industry_name` (e.g. "Facility_12") produced by Person 2/3's
geospatial pipeline (real for a genuine OSM pull, currently the MOCK
stand-in — see Phase 1/3 audits). We group anomalies by that name. There
is no other facility identity information anywhere in the repository.

KNOWN LIMITATIONS / DOCUMENTED DEFAULTS (read before trusting a field)
------------------------------------------------------------------------
- `id` / `name`: both set to the raw `nearest_industry_name` string
  (e.g. "Facility_12"). This is Person 2/3's own placeholder identifier
  from the mock OSM stand-in, NOT a real-world facility name — we do not
  invent a nicer-sounding name. A real OSM pull would carry real `name`
  tags; when that data exists, this is the one place to change.
- `location` (a human-readable string per the frontend type): no
  reverse-geocoding data exists anywhere in this repository. We use a
  coordinate string (`"{lat:.4f}, {lon:.4f}"`) as an explicitly-labelled
  placeholder — NOT a fabricated city/region name.
- `latitude` / `longitude`: the geospatial pipeline stores only the
  *distance* from an anomaly to its nearest facility, never the facility's
  own coordinates. We use the coordinates of whichever anomaly in the
  group had the smallest `distance_m` (i.e. our closest real observation
  of that facility) as the best available positional proxy.
- `type`: geospatial tokens (refinery/power_plant/oil_gas/factory/
  industrial_zone/mine/landfill) don't map 1:1 onto the frontend's 5-value
  `FacilityType` enum. See `_FACILITY_TYPE_MAP` below for the explicit,
  documented mapping — `industrial_zone` and `landfill` fall back to
  `MANUFACTURING` for lack of a closer category, and `oil_gas` maps to
  `CHEMICAL`.
- `baselineBrightness`: read directly from ml/fingerprint.py's own
  computed baseline (facility-tier mean if >= MIN_SAMPLES_FACILITY
  samples, else type-tier mean if >= MIN_SAMPLES_TYPE, else — only when
  neither has enough history — the simple mean of this facility's own
  anomalies, however few). Which tier was used is reported in `meta`
  rather than hidden.
- `normalWindow`: a brightness range built from the SAME baseline
  mean/std and ml/fingerprint.py's own `ABNORMAL_Z_THRESHOLD` /
  `ZERO_STD_MARGIN` constants (read via pipeline_adapter, not
  re-hardcoded) — this is the same math fingerprint.py itself uses to
  decide abnormal vs. normal, just rendered as a display range.
- `currentBrightness` / `detections30d` / `thermalStatus` / `riskLevel`:
  taken from whichever anomaly in the group has the most recent
  `last_detected` date — i.e. this facility's latest real observation.
- History/fingerprint endpoints never fabricate a day-by-day time series:
  each row corresponds to one genuine anomaly_id detection tied to that
  facility. A facility with only one real detection gets a one-row
  history — that sparsity is reported honestly, not padded out.
"""

from __future__ import annotations

import threading
from collections import Counter
from statistics import mean
from typing import Any

from backend.ml_integration import pipeline_adapter
from backend.services import event_service

# Geospatial nearest_industry tokens (geospatial/config.py) -> frontend
# FacilityType enum (src/types/index.ts). "none" is never a facility.
_FACILITY_TYPE_MAP = {
    "refinery": "REFINERY",
    "power_plant": "POWER PLANT",
    "oil_gas": "CHEMICAL",
    "factory": "MANUFACTURING",
    "industrial_zone": "MANUFACTURING",  # no closer category — documented fallback
    "mine": "MINING",
    "landfill": "MANUFACTURING",  # no waste-management category exists — documented fallback
}

_cache_lock = threading.Lock()
_cached_facilities: list[dict[str, Any]] | None = None
_cached_groups: dict[str, list[dict[str, Any]]] | None = None  # facility_id -> annotated rows, sorted by date


def _type_key(industry: str, land_cover: str) -> str:
    """Mirrors the EXACT format ml/fingerprint.py's own (private) _type_key()
    documents in its module docstring ("type:refinery|industrial") — not a
    reimplementation of its abnormal/normal decision logic, just matching
    the key format so we can look up the SAME baseline dict's "type" bucket
    fingerprint.py itself populated."""
    return f"type:{(industry or 'none').strip().lower()}|{(land_cover or 'unknown').strip().lower()}"


def _resolve_baseline_brightness(
    facility_id: str, rows: list[dict[str, Any]], baseline: dict[str, Any], constants: dict[str, float]
) -> tuple[float, str, int]:
    """Returns (baseline_brightness, tier_used, sample_size). tier_used is
    one of 'facility' / 'type' / 'insufficient_history' — always reported,
    never hidden, per the Phase 4 instruction that insufficient history
    must stay distinguishable rather than posing as a genuine baseline."""
    facility_stats = baseline.get("facility", {}).get(facility_id)
    if (
        facility_stats
        and facility_stats.get("n", 0) >= constants["MIN_SAMPLES_FACILITY"]
        and facility_stats.get("brightness", (None, None))[0] is not None
    ):
        return round(facility_stats["brightness"][0], 1), "facility", facility_stats["n"]

    industry_tokens = [r["raw"].get("nearest_industry") for r in rows]
    land_covers = [r["raw"].get("land_cover") for r in rows]
    dominant_industry = Counter(industry_tokens).most_common(1)[0][0] if industry_tokens else "none"
    dominant_land_cover = Counter(land_covers).most_common(1)[0][0] if land_covers else "unknown"
    type_key = _type_key(dominant_industry, dominant_land_cover)
    type_stats = baseline.get("type", {}).get(type_key)
    if (
        type_stats
        and type_stats.get("n", 0) >= constants["MIN_SAMPLES_TYPE"]
        and type_stats.get("brightness", (None, None))[0] is not None
    ):
        return round(type_stats["brightness"][0], 1), "type", type_stats["n"]

    # Neither tier has enough history — fall back to this facility's own
    # (possibly tiny) sample rather than fabricating a number.
    own_brightness = [r["raw"].get("brightness") for r in rows if r["raw"].get("brightness") is not None]
    fallback = round(mean(own_brightness), 1) if own_brightness else 0.0
    return fallback, "insufficient_history", len(rows)


def _normal_window(
    facility_id: str, baseline_brightness: float, baseline: dict[str, Any], constants: dict[str, float], tier: str
) -> tuple[float, float]:
    """Builds a (low, high) brightness band around baseline_brightness using
    ml/fingerprint.py's OWN constants — the same numbers it uses internally
    to decide abnormal vs. normal — rather than an arbitrary invented
    spread."""
    std = None
    if tier == "facility":
        std = baseline.get("facility", {}).get(facility_id, {}).get("brightness", (None, None))[1]
    if std:
        low = baseline_brightness - std
        high = baseline_brightness + constants["ABNORMAL_Z_THRESHOLD"] * std
    else:
        margin = constants["ZERO_STD_MARGIN"]
        low = baseline_brightness * (1 - margin)
        high = baseline_brightness * (1 + margin)
    return round(low, 1), round(high, 1)


def _build_facility_groups() -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for annotated in event_service.get_annotated_events():
        raw = annotated["raw"]
        nearest_industry = raw.get("nearest_industry") or "none"
        facility_id = raw.get("nearest_industry_name")
        if nearest_industry == "none" or not facility_id:
            continue
        groups.setdefault(facility_id, []).append(annotated)

    # Sort each group's rows chronologically (real last_detected dates) so
    # "most recent" and history ordering are well-defined.
    for rows in groups.values():
        rows.sort(key=lambda r: r["raw"].get("last_detected") or "")
    return groups


def _build_facility(facility_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = event_service.get_baseline()
    constants = pipeline_adapter.get_fingerprint_constants()

    nearest = min(rows, key=lambda r: r["raw"].get("distance_m") or float("inf"))
    latest = rows[-1]  # rows are sorted chronologically

    industry_tokens = [r["raw"].get("nearest_industry") for r in rows]
    dominant_industry = Counter(industry_tokens).most_common(1)[0][0] if industry_tokens else "none"
    facility_type = _FACILITY_TYPE_MAP.get(dominant_industry, "MANUFACTURING")

    baseline_brightness, tier, sample_size = _resolve_baseline_brightness(facility_id, rows, baseline, constants)
    low, high = _normal_window(facility_id, baseline_brightness, baseline, constants, tier)

    lat = nearest["raw"]["latitude"]
    lon = nearest["raw"]["longitude"]

    return {
        "id": facility_id,
        "name": facility_id,
        "type": facility_type,
        "location": f"{lat:.4f}, {lon:.4f}",
        "latitude": lat,
        "longitude": lon,
        "baselineBrightness": baseline_brightness,
        "currentBrightness": latest["raw"].get("brightness"),
        "detections30d": latest["raw"].get("detections_30d", 0),
        "persistence": round((latest["raw"].get("persistence_score") or 0) * 100, 1),
        "thermalStatus": latest["event"]["thermalStatus"],
        "normalWindow": f"{low}\u2013{high} K",
        "riskLevel": latest["event"]["riskLevel"],
        # Additional, non-breaking field (see backend/schemas/event.py's
        # pipelineMeta for the same pattern) — never hides how confident
        # the baseline actually is.
        "meta": {
            "baselineTier": tier,
            "baselineSampleSize": sample_size,
            "anomalyCount": len(rows),
            "normalWindowLow": low,
            "normalWindowHigh": high,
        },
    }


def _ensure_built() -> None:
    global _cached_facilities, _cached_groups
    if _cached_facilities is not None:
        return
    with _cache_lock:
        if _cached_facilities is None:
            groups = _build_facility_groups()
            facilities = [_build_facility(fid, rows) for fid, rows in groups.items()]
            _cached_groups = groups
            _cached_facilities = facilities


def get_facilities() -> list[dict[str, Any]]:
    _ensure_built()
    assert _cached_facilities is not None
    return _cached_facilities


def get_facility(facility_id: str) -> dict[str, Any] | None:
    for facility in get_facilities():
        if facility["id"] == facility_id:
            return facility
    return None


def get_facility_history(facility_id: str) -> list[dict[str, Any]] | None:
    """Returns FacilityHistory[] for a facility, or None if the facility
    doesn't exist. One row per REAL anomaly detection tied to this
    facility — never interpolated/fabricated days (see module docstring)."""
    _ensure_built()
    assert _cached_groups is not None
    rows = _cached_groups.get(facility_id)
    if rows is None:
        return None

    facility = get_facility(facility_id)
    assert facility is not None
    high = facility["meta"]["normalWindowHigh"]
    baseline_brightness = facility["baselineBrightness"]

    history = []
    for row in rows:
        raw = row["raw"]
        history.append(
            {
                "date": raw.get("last_detected"),
                "observedBrightness": raw.get("brightness"),
                "baseline": baseline_brightness,
                "threshold": high,
                "detectionCount": raw.get("detections_30d", 0),
                "normalWindow": facility["normalWindow"],
                "anomaly": row["event"]["thermalStatus"],
            }
        )
    return history


def get_facility_fingerprint(facility_id: str) -> dict[str, Any] | None:
    """Returns FingerprintData for a facility, or None if the facility
    doesn't exist. Built entirely from real per-anomaly rows tied to this
    facility (see module docstring) — 'frequency' is the real count of
    anomalies observed at this facility, not an invented rate."""
    _ensure_built()
    assert _cached_groups is not None
    rows = _cached_groups.get(facility_id)
    if rows is None:
        return None

    facility = get_facility(facility_id)
    assert facility is not None
    baseline_brightness = facility["baselineBrightness"]
    threshold_value = facility["meta"]["normalWindowHigh"]

    observed = [r["raw"].get("brightness") for r in rows]
    time_labels = [r["raw"].get("last_detected") for r in rows]
    latest = rows[-1]
    current_value = latest["raw"].get("brightness") or 0.0

    return {
        "facilityId": facility_id,
        "observed": observed,
        "baseline": [baseline_brightness] * len(observed),
        "threshold": [threshold_value] * len(observed),
        "timeLabels": time_labels,
        "typicalWindow": facility["normalWindow"],
        "frequency": len(rows),
        "persistence": facility["persistence"],
        "currentValue": current_value,
        "delta": round(current_value - baseline_brightness, 1),
        "status": latest["event"]["thermalStatus"],
        # Same non-breaking-extra-field pattern as ThermalEvent.pipelineMeta
        # / Facility.meta — see module docstring on why "insufficient
        # history" must stay visible rather than silently reading as a
        # confident baseline.
        "meta": facility["meta"],
    }


def refresh_facilities() -> list[dict[str, Any]]:
    """Forces a rebuild (e.g. after event_service.refresh_events() has been
    called). Not wired to any route yet."""
    global _cached_facilities, _cached_groups
    with _cache_lock:
        groups = _build_facility_groups()
        facilities = [_build_facility(fid, rows) for fid, rows in groups.items()]
        _cached_groups = groups
        _cached_facilities = facilities
    return _cached_facilities
