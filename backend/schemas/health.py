"""
Response schema for GET /api/health.

Must stay compatible with the frontend's `ApiHealth` type
(src/types/index.ts):

    export type ApiHealth = {
      status: string
      mode: 'demo' | 'live'
    }
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Simple health indicator string.")
    mode: Literal["demo", "live"] = Field(
        default="live",
        description="Tells the frontend whether it's talking to a real backend ('live') "
        "or the frontend is expected to be running against its own bundled demo data ('demo').",
    )
