"""
AgniLens - Data Squad - Person 1
=================================
Owner: NASA FIRMS ingestion, cleaning, feature extraction,
       temporal grouping ("is this the same anomaly seen again?"),
       and persistence scoring.

This is the ONLY script that is allowed to write firms_processed.csv.
Do not rename columns downstream — Squad 2 (OSM) and Squad 3 (backend)
both build against this frozen schema.

-------------------------------------------------------------------------
OUTPUT FILE:  data/processed/firms_processed.csv

FROZEN SCHEMA (do not rename / reorder / drop):
    anomaly_id         str    unique id, e.g. "ANM0001"
    latitude           float
    longitude          float
    brightness         float  mean brightness (Kelvin) across this anomaly's detections
    confidence         float  mean FIRMS confidence, 0-100
    detections_30d     int    number of detections in the trailing 30-day window
    persistence_score  float  0-1, how persistent/recurring this thermal source is
    first_detected     str    YYYY-MM-DD, earliest detection for this anomaly
    last_detected      str    YYYY-MM-DD, most recent detection for this anomaly
    n_detections_total int    total detections ever seen at this location cluster
-------------------------------------------------------------------------

USAGE
    # 1) Using a real FIRMS API key (area export, VIIRS/MODIS)
    python firms_pipeline.py --api-key YOUR_MAP_KEY \
        --area "68,6,98,38" --source VIIRS_SNPP_NRT --day-range 30

    # 2) Using an already-downloaded FIRMS CSV
    python firms_pipeline.py --input raw_firms_export.csv

    # 3) No data yet? Generate mock data so downstream squads aren't blocked
    python firms_pipeline.py --mock --n-mock 300
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0088
DEFAULT_CLUSTER_RADIUS_KM = 1.0   # detections within this radius = same anomaly
DEFAULT_WINDOW_DAYS = 30          # trailing window for "detections_30d"

RAW_DIR = os.path.join("data", "raw")
PROCESSED_DIR = os.path.join("data", "processed")


# --------------------------------------------------------------------------
# 1. Ingest
# --------------------------------------------------------------------------

def fetch_firms_from_api(api_key: str, area: str, source: str = "VIIRS_SNPP_NRT",
                          day_range: int = 30, date: str | None = None) -> pd.DataFrame:
    """
    Pull an area export straight from the NASA FIRMS API.

    area:   "west,south,east,north" bounding box, e.g. "68,6,98,38" for India
    source: e.g. VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, MODIS_NRT
    """
    date_part = f"/{date}" if date else ""
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{api_key}/{source}/{area}/{day_range}{date_part}"
    )
    df = pd.read_csv(url)
    return df


def load_firms_csv(path: str) -> pd.DataFrame:
    """Load a FIRMS export already sitting on disk."""
    return pd.read_csv(path)


def generate_mock_firms_data(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """
    Produce a synthetic-but-realistic FIRMS-shaped dataframe so the AI and
    Product squads can start building against the real column names on Day 1,
    without waiting on API access or a live download.
    """
    rng = np.random.default_rng(seed)

    # A handful of "hotspot centers" that will each generate a cluster of
    # repeat detections (simulating persistent industrial sources), plus
    # scattered one-off points (simulating wildfires / stubble burning).
    n_centers = max(3, n // 25)
    center_lats = rng.uniform(20.0, 30.0, n_centers)
    center_lons = rng.uniform(72.0, 88.0, n_centers)

    rows = []
    today = datetime.now(timezone.utc).date()

    for i in range(n):
        if rng.random() < 0.7 and n_centers > 0:
            # detection near an existing hotspot -> repeat/persistent behaviour
            c = rng.integers(0, n_centers)
            lat = center_lats[c] + rng.normal(0, 0.01)
            lon = center_lons[c] + rng.normal(0, 0.01)
            brightness = rng.normal(345, 8)
            days_ago = rng.integers(0, 60)
        else:
            # scattered one-off detection
            lat = rng.uniform(8.0, 35.0)
            lon = rng.uniform(68.0, 97.0)
            brightness = rng.normal(320, 15)
            days_ago = rng.integers(0, 60)

        acq_date = today - timedelta(days=int(days_ago))
        rows.append({
            "latitude": round(float(lat), 5),
            "longitude": round(float(lon), 5),
            "brightness": round(float(brightness), 1),
            "scan": round(rng.uniform(0.3, 1.2), 2),
            "track": round(rng.uniform(0.3, 1.2), 2),
            "acq_date": acq_date.isoformat(),
            "acq_time": f"{rng.integers(0, 24):02d}{rng.integers(0, 60):02d}",
            "satellite": rng.choice(["N", "1", "Terra", "Aqua"]),
            "instrument": rng.choice(["VIIRS", "MODIS"]),
            "confidence": int(np.clip(rng.normal(75, 15), 20, 100)),
            "version": "2.0NRT",
            "bright_t31": round(float(brightness) - rng.uniform(5, 20), 1),
            "frp": round(rng.uniform(1, 60), 1),
            "daynight": rng.choice(["D", "N"]),
        })

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 2. Clean
# --------------------------------------------------------------------------

def clean_firms_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize dtypes, drop junk rows, keep only what downstream needs.
    Tolerant of both MODIS and VIIRS FIRMS export column sets.
    """
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    required = ["latitude", "longitude", "acq_date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"FIRMS export is missing required columns: {missing}")

    # Numeric coercion — bad rows become NaN then get dropped
    for col in ["latitude", "longitude", "brightness", "confidence", "frp", "bright_t31"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # VIIRS sometimes reports confidence as low/nominal/high instead of a number
    if "confidence" in df.columns and df["confidence"].dtype == object:
        conf_map = {"l": 30, "low": 30, "n": 60, "nominal": 60, "h": 90, "high": 90}
        df["confidence"] = (
            df["confidence"].astype(str).str.lower().map(conf_map).fillna(60)
        )

    df["acq_date"] = pd.to_datetime(df["acq_date"], errors="coerce")

    df = df.dropna(subset=["latitude", "longitude", "acq_date"])
    df = df[(df["latitude"].between(-90, 90)) & (df["longitude"].between(-180, 180))]

    if "confidence" in df.columns:
        df["confidence"] = df["confidence"].fillna(df["confidence"].median())
    else:
        df["confidence"] = 60.0

    if "brightness" not in df.columns:
        df["brightness"] = df.get("bright_ti4", np.nan)
    df["brightness"] = df["brightness"].fillna(df["brightness"].median())

    df = df.drop_duplicates(subset=["latitude", "longitude", "acq_date"])
    df = df.reset_index(drop=True)
    return df


# --------------------------------------------------------------------------
# 3. Temporal / spatial grouping into "anomalies"
# --------------------------------------------------------------------------

def _haversine_radians(coords_deg: np.ndarray) -> np.ndarray:
    return np.radians(coords_deg)


def cluster_into_anomalies(
    df: pd.DataFrame,
    eps_km: float = DEFAULT_CLUSTER_RADIUS_KM,
    min_samples: int = 1,
) -> pd.DataFrame:
    """
    Group individual FIRMS detections that represent the *same* real-world
    thermal source (repeat satellite passes over the same refinery, flare,
    or fire) into a single anomaly cluster, using DBSCAN with haversine
    distance. Detections more than `eps_km` apart are treated as distinct
    sources.
    """
    coords = _haversine_radians(df[["latitude", "longitude"]].to_numpy())
    eps_rad = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine")
    labels = db.fit_predict(coords)

    df = df.copy()
    df["cluster_id"] = labels
    # DBSCAN noise (-1) means a singleton detection with no neighbors within
    # eps_km — still a valid, standalone anomaly, just give each its own id.
    noise_mask = df["cluster_id"] == -1
    max_label = df["cluster_id"].max()
    new_ids = np.arange(max_label + 1, max_label + 1 + noise_mask.sum())
    df.loc[noise_mask, "cluster_id"] = new_ids

    return df


# --------------------------------------------------------------------------
# 4. Persistence calculation
# --------------------------------------------------------------------------

def compute_persistence(
    df: pd.DataFrame,
    window_days: int = DEFAULT_WINDOW_DAYS,
    reference_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    For every clustered anomaly, compute:
      - detections_30d      : count of detections within the trailing window
      - n_detections_total  : total detections ever seen in this cluster
      - persistence_score   : 0-1 score — higher means this location keeps
                              lighting up over a long span, not a one-off.

    persistence_score blends two signals:
      * frequency  = detections in window / window_days (capped at 1.0 after scaling)
      * span_ratio = (last_detected - first_detected) / window_days, capped at 1.0
    A single one-off detection scores ~0. A source detected on most days
    across the whole window scores close to 1.
    """
    if reference_date is None:
        reference_date = df["acq_date"].max()

    window_start = reference_date - pd.Timedelta(days=window_days)

    records = []
    for cluster_id, g in df.groupby("cluster_id"):
        g = g.sort_values("acq_date")
        first_detected = g["acq_date"].min()
        last_detected = g["acq_date"].max()
        total = len(g)

        recent = g[g["acq_date"] >= window_start]
        detections_30d = len(recent)

        span_days = max((last_detected - first_detected).days, 0)
        span_ratio = min(span_days / window_days, 1.0)
        freq_ratio = min(detections_30d / window_days, 1.0)

        # weight frequency a bit higher than raw span — a source detected
        # daily for 10 days is more "persistent" in the operational sense
        # than one detected twice, 29 days apart.
        persistence_score = round(0.6 * freq_ratio + 0.4 * span_ratio, 3)

        records.append({
            "cluster_id": cluster_id,
            "latitude": round(g["latitude"].mean(), 5),
            "longitude": round(g["longitude"].mean(), 5),
            "brightness": round(g["brightness"].mean(), 1),
            "confidence": round(g["confidence"].mean(), 1),
            "detections_30d": int(detections_30d),
            "n_detections_total": int(total),
            "persistence_score": persistence_score,
            "first_detected": first_detected.date().isoformat(),
            "last_detected": last_detected.date().isoformat(),
        })

    return pd.DataFrame(records)


# --------------------------------------------------------------------------
# 5. Build final frozen-schema table
# --------------------------------------------------------------------------

def build_anomaly_table(raw_df: pd.DataFrame,
                         eps_km: float = DEFAULT_CLUSTER_RADIUS_KM,
                         window_days: int = DEFAULT_WINDOW_DAYS) -> pd.DataFrame:
    cleaned = clean_firms_data(raw_df)
    clustered = cluster_into_anomalies(cleaned, eps_km=eps_km)
    anomalies = compute_persistence(clustered, window_days=window_days)

    # Assign the public-facing anomaly_id (this is what Squad 2/3 join on)
    anomalies = anomalies.sort_values("last_detected", ascending=False).reset_index(drop=True)
    anomalies["anomaly_id"] = [f"ANM{idx+1:04d}" for idx in anomalies.index]

    final = anomalies[[
        "anomaly_id",
        "latitude",
        "longitude",
        "brightness",
        "confidence",
        "detections_30d",
        "persistence_score",
        "first_detected",
        "last_detected",
        "n_detections_total",
    ]]
    return final


# --------------------------------------------------------------------------
# 6. Basic sanity checks — run before handing off to Squad 2
# --------------------------------------------------------------------------

def validate_schema(df: pd.DataFrame) -> None:
    required_cols = [
        "anomaly_id", "latitude", "longitude", "brightness", "confidence",
        "detections_30d", "persistence_score", "first_detected",
        "last_detected", "n_detections_total",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise AssertionError(f"Output is missing frozen-schema columns: {missing}")

    assert df["anomaly_id"].is_unique, "anomaly_id must be unique per row"
    assert df["latitude"].between(-90, 90).all(), "latitude out of range"
    assert df["longitude"].between(-180, 180).all(), "longitude out of range"
    assert df["persistence_score"].between(0, 1).all(), "persistence_score must be 0-1"
    assert (df["detections_30d"] >= 0).all(), "detections_30d must be >= 0"
    print(f"[OK] Schema valid. {len(df)} anomalies ready for Squad 2.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AgniLens Person 1: FIRMS data pipeline")
    parser.add_argument("--input", type=str, help="Path to a raw FIRMS CSV already on disk")
    parser.add_argument("--api-key", type=str, help="NASA FIRMS MAP_KEY for live API pull")
    parser.add_argument("--area", type=str, default="68,6,98,38",
                         help="west,south,east,north bounding box (default: India)")
    parser.add_argument("--source", type=str, default="VIIRS_SNPP_NRT",
                         help="FIRMS source, e.g. VIIRS_SNPP_NRT, MODIS_NRT")
    parser.add_argument("--day-range", type=int, default=30)
    parser.add_argument("--mock", action="store_true", help="Generate synthetic FIRMS data")
    parser.add_argument("--n-mock", type=int, default=300)
    parser.add_argument("--eps-km", type=float, default=DEFAULT_CLUSTER_RADIUS_KM,
                         help="Radius (km) within which repeat detections = same anomaly")
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--outdir", type=str, default=PROCESSED_DIR)
    args = parser.parse_args()

    if args.mock:
        print(f"[INFO] Generating {args.n_mock} mock FIRMS detections...")
        raw_df = generate_mock_firms_data(n=args.n_mock)
    elif args.input:
        print(f"[INFO] Loading raw FIRMS export from {args.input}")
        raw_df = load_firms_csv(args.input)
    elif args.api_key:
        print(f"[INFO] Pulling live FIRMS data for area={args.area}, source={args.source}")
        raw_df = fetch_firms_from_api(
            api_key=args.api_key, area=args.area,
            source=args.source, day_range=args.day_range,
        )
    else:
        print("[ERROR] Provide one of --mock, --input, or --api-key. Use --mock to unblock "
              "the other squads immediately.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(args.outdir, exist_ok=True)

    raw_path = os.path.join(RAW_DIR, "firms_raw.csv")
    raw_df.to_csv(raw_path, index=False)
    print(f"[INFO] Raw data saved -> {raw_path} ({len(raw_df)} rows)")

    final_df = build_anomaly_table(raw_df, eps_km=args.eps_km, window_days=args.window_days)
    validate_schema(final_df)

    out_path = os.path.join(args.outdir, "firms_processed.csv")
    final_df.to_csv(out_path, index=False)
    print(f"[INFO] Processed anomalies saved -> {out_path}")
    print(final_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
