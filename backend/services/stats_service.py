"""
backend/services/stats_service.py

GET /api/stats must mirror exactly what src/api/client.ts's getStats()
computes in demo mode from demoEvents/facilities — same four fields, same
definitions — just computed from the REAL backend-derived events/facilities
instead of the static demo arrays. No independent statistics, no
hard-coded dashboard numbers: this reuses event_service.get_events() and
facility_service.get_facilities() (which themselves reuse the exact same
ml/pipeline.py output events/facilities are built from).
"""

from __future__ import annotations

from typing import Any

from backend.services import event_service, facility_service


def get_stats() -> dict[str, Any]:
    events = event_service.get_events()
    facilities = facility_service.get_facilities()

    abnormal = sum(1 for e in events if e["thermalStatus"] == "ABNORMAL")
    # Matches src/App.tsx CommandCenterPage's own definition of "high/critical"
    # (riskLevel HIGH or CRITICAL) rather than client.ts's demo-mode getStats()
    # (which only counts CRITICAL) — CommandCenterPage is the live dashboard
    # consumer, so its definition is the one this field needs to agree with.
    high_critical = sum(1 for e in events if e["riskLevel"] in ("HIGH", "CRITICAL"))

    return {
        "thermalEvents": len(events),
        "abnormal": abnormal,
        "highCritical": high_critical,
        "facilitiesMonitored": len(facilities),
    }
