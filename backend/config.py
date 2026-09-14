"""
backend/config.py

Single source of truth for backend configuration. Reads from environment
variables (optionally via a .env file) so local dev / demo / deployment can
differ without code changes.

Deliberately minimal for Phase 2 (backend foundation only). Data-source
paths (firms_processed.csv, anomaly_features.csv, ml/ model artifacts) will
be added here in a later phase once the data adapter / ML integration work
begins — do not add them speculatively now.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend._repo_root import REPO_ROOT

__all__ = ["Settings", "get_settings", "REPO_ROOT"]


class Settings(BaseSettings):
    """
    Backend settings. Values can be overridden via environment variables
    (e.g. AGNINETRA_APP_NAME=... ) or a `.env` file in the repository root.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGNINETRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AgniNetra Backend"
    api_mode: str = "live"  # reported to the frontend via /api/health -> mode

    # Local Vite dev server defaults (see vite.config.ts / package.json).
    # Comma-separated list, overridable via AGNINETRA_CORS_ORIGINS env var.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import and call this, don't instantiate Settings() directly."""
    return Settings()
