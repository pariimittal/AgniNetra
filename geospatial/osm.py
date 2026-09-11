"""
THERMOS — Squad 1 / Person 2 (OSM + Geospatial Features)
osm.py

Fetches OSM industrial infrastructure and landuse/land-cover-proxy polygons
for a bounding box via the Overpass API.

NOTE ON NETWORK: this needs to reach overpass-api.de (or a mirror) which
isn't reachable from my current sandbox, so this file is written correctly
but only exercised here against mocked responses (see test_features.py).
Run it for real in your own dev environment / CI.

Usage:
    from osm import fetch_industrial_facilities, fetch_landuse_polygons
    facilities = fetch_industrial_facilities(bbox=(south, west, north, east))
    landuse = fetch_landuse_polygons(bbox=(south, west, north, east))
"""

import time
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from config import OSM_INDUSTRIAL_TAGS, LANDCOVER_TAGS, DEFAULT_LANDCOVER

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Fallback mirrors — Overpass' main instance rate-limits hard; rotate if needed
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def _bbox_str(bbox):
    """bbox = (south, west, north, east) -> Overpass bbox string."""
    south, west, north, east = bbox
    return f"{south},{west},{north},{east}"


def _run_overpass_query(query, timeout=90, retries=3):
    last_err = None
    headers = {
        "User-Agent": "AgniNetra-THERMOS-SIH-Prototype/1.0 (student project)",
        "Accept": "application/json, text/plain, */*",
    }
    for mirror in OVERPASS_MIRRORS:
        for attempt in range(retries):
            try:
                resp = requests.post(mirror, data={"data": query}, headers=headers, timeout=timeout)
                resp.raise_for_status()
                result = resp.json()
                # Overpass sometimes returns HTTP 200 with an embedded error
                # instead of a proper HTTP error code — catch that here.
                if "remark" in result and "elements" not in result:
                    raise RuntimeError(f"Overpass server error: {result['remark']}")
                print(f"  [Overpass OK via {mirror}, attempt {attempt+1}] "
                      f"{len(result.get('elements', []))} elements")
                return result
            except Exception as e:
                last_err = e
                print(f"  [Overpass failed via {mirror}, attempt {attempt+1}]: {e}")
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Overpass query failed on all mirrors: {last_err}")


def fetch_industrial_facilities(bbox) -> gpd.GeoDataFrame:
    """
    Fetch industrial facility points/polygons (power plants, refineries,
    factories, mines, landfills, etc.) within bbox.

    Returns a GeoDataFrame with columns:
        osm_id, name, facility_type (normalized via config.OSM_INDUSTRIAL_TAGS),
        raw_tags, geometry (Point — polygon centroids are used for area features)
    """
    bstr = _bbox_str(bbox)
    clauses = []
    for (key, val) in OSM_INDUSTRIAL_TAGS.keys():
        clauses.append(f'node["{key}"="{val}"]({bstr});')
        clauses.append(f'way["{key}"="{val}"]({bstr});')
        clauses.append(f'relation["{key}"="{val}"]({bstr});')

    query = f"""
    [out:json][timeout:90];
    (
      {' '.join(clauses)}
    );
    out center tags;
    """

    data = _run_overpass_query(query)
    records = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        facility_type = None
        for (key, val), norm in OSM_INDUSTRIAL_TAGS.items():
            if tags.get(key) == val:
                facility_type = norm
                break
        if facility_type is None:
            continue

        if el["type"] == "node":
            lat, lon = el["lat"], el["lon"]
        else:
            center = el.get("center")
            if not center:
                continue
            lat, lon = center["lat"], center["lon"]

        records.append({
            "osm_id": f'{el["type"]}/{el["id"]}',
            "name": tags.get("name", "unnamed"),
            "facility_type": facility_type,
            "raw_tags": tags,
            "geometry": Point(lon, lat),
        })

    if records:
        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    else:
        gdf = gpd.GeoDataFrame(
            columns=["osm_id", "name", "facility_type", "raw_tags", "geometry"],
            geometry="geometry", crs="EPSG:4326"
        )
    return gdf


def fetch_landuse_polygons(bbox) -> gpd.GeoDataFrame:
    """
    Fetch landuse/natural polygons used as a land-cover proxy (forest,
    agricultural, industrial, residential, water, mining).

    Returns a GeoDataFrame with columns: osm_id, land_cover, geometry (Polygon)
    """
    bstr = _bbox_str(bbox)
    clauses = []
    for (key, val) in LANDCOVER_TAGS.keys():
        clauses.append(f'way["{key}"="{val}"]({bstr});')
        clauses.append(f'relation["{key}"="{val}"]({bstr});')

    query = f"""
    [out:json][timeout:90];
    (
      {' '.join(clauses)}
    );
    out geom;
    """

    data = _run_overpass_query(query)
    records = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        land_cover = DEFAULT_LANDCOVER
        for (key, val), norm in LANDCOVER_TAGS.items():
            if tags.get(key) == val:
                land_cover = norm
                break
        if land_cover == DEFAULT_LANDCOVER:
            continue

        geom_pts = el.get("geometry")
        if not geom_pts or len(geom_pts) < 3:
            continue
        poly = Polygon([(p["lon"], p["lat"]) for p in geom_pts])
        if not poly.is_valid or poly.is_empty:
            continue

        records.append({
            "osm_id": f'{el["type"]}/{el["id"]}',
            "land_cover": land_cover,
            "geometry": poly,
        })

    if records:
        gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    else:
        gdf = gpd.GeoDataFrame(
            columns=["osm_id", "land_cover", "geometry"],
            geometry="geometry", crs="EPSG:4326"
        )
    return gdf