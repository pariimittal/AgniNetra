"""
backend/_repo_root.py

Computes the absolute repository-root path with ZERO third-party
dependencies (stdlib `os` only). Deliberately separated from
`backend/config.py` (which needs `pydantic-settings`) so that low-level,
dependency-light modules — like `backend/data_access/paths.py` and
`backend/ml_integration/pipeline_adapter.py` — can resolve paths and be unit
tested even in an environment where `pydantic`/`fastapi` aren't installed
yet (see Phase 2 audit note on this sandbox's lack of network access).

`backend/config.py` re-exports REPO_ROOT from here rather than
recomputing it, so there is exactly one definition.
"""

from __future__ import annotations

import os

# backend/_repo_root.py -> backend/ -> <repo root>
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
