"""
backend/schemas/stats.py

Matches the shape src/api/client.ts's getStats() returns in demo mode
(there's no dedicated TS type for it in src/types/index.ts — client.ts
builds the object inline):

    { thermalEvents, abnormal, highCritical, facilitiesMonitored }
"""

from __future__ import annotations

from pydantic import BaseModel


class Stats(BaseModel):
    thermalEvents: int
    abnormal: int
    highCritical: int
    facilitiesMonitored: int
