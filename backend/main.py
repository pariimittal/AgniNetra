"""
backend/main.py — AgniNetra FastAPI entrypoint.

Run from the REPOSITORY ROOT (not from inside backend/):

    uvicorn backend.main:app --reload

This exposes the FastAPI app as `backend.main:app`. Do not `cd backend`
first — the package uses absolute `backend.xxx` imports.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import events, facilities, health, stats
from backend.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Integration layer connecting the AgniNetra frontend GIS dashboard "
        "to the FIRMS/geospatial/ML/risk components developed independently "
        "by the rest of the team."
    ),
    version="0.1.0",
)

# CORS: allow the local Vite dev server (see .env.example / vite.config.ts)
# to call this API during development. Override AGNINETRA_CORS_ORIGINS in
# the environment for other setups (e.g. a deployed frontend origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every route in this API is namespaced under /api to match the frontend's
# src/api/client.ts, which calls `${API_BASE_URL}/api/...`.
app.include_router(health.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(facilities.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Bare-minimum landing response so hitting the root URL isn't a 404."""
    return {"service": settings.app_name, "docs": "/docs"}
