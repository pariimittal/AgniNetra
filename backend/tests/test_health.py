"""
Minimal Phase-2 backend test.

Run from the repository root:

    pytest backend/tests/test_health.py -v

Verifies:
  1. backend.main imports successfully (i.e. the package/app wires up
     without errors).
  2. GET /api/health returns HTTP 200.
  3. The response body matches the shape the frontend's `ApiHealth` type
     expects: {"status": str, "mode": "demo" | "live"}.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_backend_imports_successfully() -> None:
    """If backend.main failed to import, this whole test module would already
    have failed at collection time — this test just makes that intent explicit."""
    assert app is not None


def test_health_returns_200() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_response_shape() -> None:
    response = client.get("/api/health")
    body = response.json()

    assert "status" in body
    assert "mode" in body
    assert isinstance(body["status"], str)
    assert body["mode"] in ("demo", "live")

    # Matches the exact example given in the Phase 2 spec.
    assert body == {"status": "ok", "mode": "live"}
