"""
AgniNetra backend package.

This package is the integration layer between the frontend GIS dashboard
and the independently developed data / geospatial / ML components that
live at the repository root (firms_pipeline.py, geospatial/, ml/).

Run from the REPOSITORY ROOT with:

    uvicorn backend.main:app --reload

Do not `cd backend` and run `uvicorn main:app` — the package uses absolute
imports (`backend.xxx`) so it must be importable as `backend` from the
current working directory / PYTHONPATH.
"""
