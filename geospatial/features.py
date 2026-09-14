"""
THERMOS — Squad 1 / Person 2 (OSM + Geospatial Features)
features.py

Core job: "Given this FIRMS point, what is around it?"

Takes:
  - firms_df: cleaned FIRMS points from Squad 1 / Person 1
              (must have columns: anomaly_id, latitude, longitude)
  - facilities_gdf: from osm.fetch_industrial_facilities()
  - landuse_gdf: from osm.fetch_landuse_polygons()
  - population_df (optional): point-based population proxy, columns
              [latitude, longitude, population] — plug in WorldPop/GHSL
              extraction later; a stub is provided so the pipeline runs
              end-to-end before that data source is wired in.

Produces anomaly_features.csv matching config.OUTPUT_SCHEMA_COLUMNS —
this is Squad 1's contractual output to Squad 2 (AI/ML). Do not change
column names without updating config.py and notifying the Integration Lead.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.neighbors import BallTree

from config import (
    OUTPUT_SCHEMA_COLUMNS,
    INCLUDE_POPULATION_PROXIMITY,
    DIST_VERY_CLOSE_M,
    DIST_NEARBY_M,
    POP_HIGH_PROXIMITY_M,
    POP_MEDIUM_PROXIMITY_M,
    DEFAULT_LANDCOVER,
)

EARTH_RADIUS_M = 6_371_000


def _to_radians(lat_series, lon_series):
    return np.radians(np.column_stack([lat_series.values, lon_series.values]))


def _build_balltree(gdf: gpd.GeoDataFrame):
    """BallTree over lat/lon (as radians) using haversine metric."""
    lats = gdf.geometry.y
    lons = gdf.geometry.x
    coords_rad = _to_radians(lats, lons)
    tree = BallTree(coords_rad, metric="haversine")
    return tree


def nearest_facility(firms_df: pd.DataFrame, facilities_gdf: gpd.GeoDataFrame):
    """
    For each FIRMS point, find the nearest industrial facility.
    Returns arrays: facility_type, facility_name, distance_m
    """
    n = len(firms_df)
    if facilities_gdf is None or len(facilities_gdf) == 0:
        return (np.array(["none"] * n), np.array(["none"] * n),
                np.full(n, np.inf))

    tree = _build_balltree(facilities_gdf)
    query_rad = _to_radians(firms_df["latitude"], firms_df["longitude"])
    dist_rad, idx = tree.query(query_rad, k=1)

    distance_m = dist_rad[:, 0] * EARTH_RADIUS_M
    idx = idx[:, 0]

    facility_type = facilities_gdf.iloc[idx]["facility_type"].values
    facility_name = facilities_gdf.iloc[idx]["name"].values
    return facility_type, facility_name, distance_m


def nearest_forest_km(firms_df: pd.DataFrame, landuse_gdf: gpd.GeoDataFrame):
    """
    Distance in km from each FIRMS point to the nearest forest polygon
    centroid. (Cheap centroid-distance approximation — fine for triage;
    swap for true polygon-boundary distance if precision matters later.)
    """
    n = len(firms_df)
    if landuse_gdf is None or len(landuse_gdf) == 0:
        return np.full(n, np.nan)

    forest_gdf = landuse_gdf[landuse_gdf["land_cover"] == "forest"].copy()
    if len(forest_gdf) == 0:
        return np.full(n, np.nan)

    # Reproject to a projected CRS (Web Mercator) before centroid calc —
    # centroids on raw lat/lon polygons are distorted at scale.
    forest_gdf["geometry"] = (
        forest_gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
    )
    tree = _build_balltree(forest_gdf)
    query_rad = _to_radians(firms_df["latitude"], firms_df["longitude"])
    dist_rad, _ = tree.query(query_rad, k=1)
    return (dist_rad[:, 0] * EARTH_RADIUS_M) / 1000.0


def land_cover_at_point(firms_df: pd.DataFrame, landuse_gdf: gpd.GeoDataFrame):
    """
    Point-in-polygon lookup: which landuse polygon (if any) contains each
    FIRMS point. Falls back to DEFAULT_LANDCOVER ('unknown') when no
    polygon covers the point — expected/common, not an error.
    """
    n = len(firms_df)
    if landuse_gdf is None or len(landuse_gdf) == 0:
        return np.array([DEFAULT_LANDCOVER] * n)

    points_gdf = gpd.GeoDataFrame(
        firms_df.copy(),
        geometry=gpd.points_from_xy(firms_df["longitude"], firms_df["latitude"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points_gdf, landuse_gdf[["land_cover", "geometry"]],
                        how="left", predicate="within")
    # sjoin can duplicate rows if polygons overlap — keep first match per point
    joined = joined[~joined.index.duplicated(keep="first")]
    land_cover = joined["land_cover"].fillna(DEFAULT_LANDCOVER).values
    return land_cover


def population_proximity(firms_df: pd.DataFrame, population_df: pd.DataFrame = None):
    """
    STUB: population context is not yet wired to a real data source
    (WorldPop / GHSL). Nobody in the current squad plan owns this input —
    flag to the team. Until then, returns 'unknown' for every point so
    downstream consumers (risk engine) get a real, non-crashing value.

    Once population_df is available (columns: latitude, longitude,
    population), this does a nearest-point lookup and buckets into
    high / medium / low using POP_HIGH_PROXIMITY_M / POP_MEDIUM_PROXIMITY_M.
    """
    n = len(firms_df)
    if population_df is None or len(population_df) == 0:
        return np.array(["unknown"] * n)

    pop_gdf = gpd.GeoDataFrame(
        population_df.copy(),
        geometry=gpd.points_from_xy(population_df["longitude"], population_df["latitude"]),
        crs="EPSG:4326",
    )
    tree = _build_balltree(pop_gdf)
    query_rad = _to_radians(firms_df["latitude"], firms_df["longitude"])
    dist_rad, idx = tree.query(query_rad, k=1)
    distance_m = dist_rad[:, 0] * EARTH_RADIUS_M

    bands = np.where(
        distance_m <= POP_HIGH_PROXIMITY_M, "high",
        np.where(distance_m <= POP_MEDIUM_PROXIMITY_M, "medium", "low")
    )
    return bands


def compute_features(firms_df: pd.DataFrame,
                      facilities_gdf: gpd.GeoDataFrame,
                      landuse_gdf: gpd.GeoDataFrame,
                      population_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Main entry point. Given a cleaned FIRMS dataframe (from Person 1) plus
    OSM facility/landuse data (from this module's fetch functions), produce
    the standardized anomaly_features.csv output.
    """
    required_cols = {"anomaly_id", "latitude", "longitude"}
    missing = required_cols - set(firms_df.columns)
    if missing:
        raise ValueError(f"firms_df missing required columns: {missing}")

    facility_type, facility_name, distance_m = nearest_facility(firms_df, facilities_gdf)
    forest_km = nearest_forest_km(firms_df, landuse_gdf)
    land_cover = land_cover_at_point(firms_df, landuse_gdf)

    out = pd.DataFrame({
        "anomaly_id": firms_df["anomaly_id"].values,
        "latitude": firms_df["latitude"].values,
        "longitude": firms_df["longitude"].values,
        "nearest_industry": facility_type,
        "nearest_industry_name": facility_name,
        "distance_m": np.round(distance_m, 1),
        "land_cover": land_cover,
        "nearest_forest_km": np.round(forest_km, 2),
    })

    # Only compute + attach population_proximity if a real data source is
    # wired in (config.INCLUDE_POPULATION_PROXIMITY). Currently False by
    # team decision — see config.py comment. Shipping a constant "unknown"
    # column wastes a BallTree build for zero signal, so skip it entirely
    # rather than compute-then-drop.
    if INCLUDE_POPULATION_PROXIMITY:
        out["population_proximity"] = population_proximity(firms_df, population_df)

    return out[OUTPUT_SCHEMA_COLUMNS]
