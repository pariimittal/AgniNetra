"""
Adapter layer around the repo-root `ml/` package (classification, thermal
fingerprint, and risk engine — see ml/pipeline.py's `process_anomaly()` /
`build_baseline_from_history()`).

Named `ml_integration` (not `ml`) deliberately, so it never shadows or gets
confused with the repository-root `ml/` package that Person 3 / Person 4
own — `backend` code should import the real one as a top-level `ml` module
(with `ml/` on `sys.path`, resolved relative to backend.config.REPO_ROOT)
and wrap it here, not reimplement it.

Empty in Phase 2 (backend foundation only). Do NOT wire up ml/pipeline.py
here yet — that is explicit future-phase work (see Phase 1 audit, section
E10, on the working-directory coupling that needs to be solved first).
"""
