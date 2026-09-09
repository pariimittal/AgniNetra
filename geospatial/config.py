"""
THERMOS — Squad 1 / Person 2 (OSM + Geospatial Features)
config.py

Single source of truth for:
  - distance thresholds (must match what AI squad / risk engine assumes)
  - OSM tag -> facility_type taxonomy (aligned with ML classification classes)
  - land-cover categories (aligned with OSM landuse/natural tags)

IMPORTANT: If these thresholds or category names change, tell Squad 2 (AI/ML)
and the Integration Lead immediately — risk scoring and classification both
depend on these values matching what they expect.
"""

# ---------------------------------------------------------------------------
# Distance thresholds (meters) — used to decide "is this FIRMS point AT/NEAR
# a facility" vs "isolated / natural area"
# ---------------------------------------------------------------------------
DIST_VERY_CLOSE_M = 500       # essentially co-located with facility
DIST_NEARBY_M = 2000          # plausibly influenced by facility (e.g. flare glow, sprawl)
DIST_REGIONAL_M = 10000       # same industrial zone but not directly attributable

# Population proximity bands (meters) — crude, refine once real population
# raster/point data is wired in (see fetch_population_context stub below)
POP_HIGH_PROXIMITY_M = 3000
POP_MEDIUM_PROXIMITY_M = 10000

# ---------------------------------------------------------------------------
# OSM industrial facility taxonomy
# Maps raw OSM tag values -> a normalized facility_type used everywhere
# downstream (features, model, dashboard). Extend this dict, don't invent
# new ad-hoc strings elsewhere in the codebase.
# ---------------------------------------------------------------------------
OSM_INDUSTRIAL_TAGS = {
    # (osm_key, osm_value) : normalized facility_type
    ("power", "plant"): "power_plant",
    ("power", "generator"): "power_plant",
    ("man_made", "petroleum_well"): "oil_gas",
    ("man_made", "gasometer"): "oil_gas",
    ("man_made", "works"): "factory",
    ("industrial", "refinery"): "refinery",
    ("landuse", "industrial"): "industrial_zone",
    ("industrial", "oil"): "refinery",
    ("industrial", "gas"): "oil_gas",
    ("man_made", "mineshaft"): "mine",
    ("landuse", "quarry"): "mine",
    ("man_made", "chimney"): "factory",
    ("amenity", "waste_disposal"): "landfill",
    ("landuse", "landfill"): "landfill",
}

# Overpass query fragment for each relevant key — used by osm.py to build
# the Overpass QL request in one shot per bounding box.
OVERPASS_KEYS = ["power", "man_made", "industrial", "landuse", "amenity"]

# ---------------------------------------------------------------------------
# Land cover proxy via OSM landuse / natural tags
# (Decision: using OSM polygons instead of a raster land-cover product like
#  ESA WorldCover for hackathon timeline — no GDAL/raster pipeline needed.
#  Flag to team: coverage will be patchy in some regions; "unknown" is a
#  valid and expected output, not a bug.)
# ---------------------------------------------------------------------------
LANDCOVER_TAGS = {
    ("landuse", "forest"): "forest",
    ("natural", "wood"): "forest",
    ("landuse", "farmland"): "agricultural",
    ("landuse", "meadow"): "agricultural",
    ("landuse", "industrial"): "industrial",
    ("landuse", "residential"): "residential",
    ("natural", "water"): "water",
    ("landuse", "quarry"): "mining",
}

DEFAULT_LANDCOVER = "unknown"

# ---------------------------------------------------------------------------
# DECISION (2026-09-09): population_proximity has no real data source wired
# in yet (see features.py population_proximity() — it's a stub). Shipping a
# column that's constantly "unknown" teaches the AI model nothing and just
# wastes debugging time on Squad 2's side, so it's EXCLUDED from output by
# default. Flip this to True the moment someone owns sourcing real
# population data (WorldPop / GHSL) and wires it into population_df.
# ---------------------------------------------------------------------------
INCLUDE_POPULATION_PROXIMITY = False

# ---------------------------------------------------------------------------
# DEMO BOUNDING BOX
# *** PLACEHOLDER — TEAM MUST CONFIRM THIS BEFORE THE REAL DATA PULL ***
#
# Stored as named fields, not a bare tuple, on purpose: Person 1's FIRMS
# script and this module's Overpass calls want the SAME area in TWO
# DIFFERENT string orderings, and a bare (a, b, c, d) tuple is exactly how
# that gets mixed up between squads.
#   - FIRMS API expects:    "west,south,east,north"   (Person 1's --area)
#   - Overpass API expects: south,west,north,east     (used internally by osm.py)
# Set the box ONCE here; use bbox_to_firms_area() / bbox_to_overpass() below
# rather than typing either string out by hand anywhere else in the codebase.
# ---------------------------------------------------------------------------
DEMO_BBOX = {
    "south": 28.40,
    "west": 77.00,
    "north": 28.70,
    "east": 77.40,
}  # example: Delhi-NCR industrial belt — CONFIRM WITH TEAM


def bbox_to_overpass(bbox=None):
    """(south, west, north, east) tuple, as osm.py's Overpass queries expect."""
    b = bbox or DEMO_BBOX
    return (b["south"], b["west"], b["north"], b["east"])


def bbox_to_firms_area(bbox=None):
    """
    "west,south,east,north" string, exactly matching Person 1's
    firms_pipeline.py --area argument format. Pass this straight to
    Person 1's script rather than retyping the box in that ordering by hand:
        python firms_pipeline.py --area "$(python -c 'from config import bbox_to_firms_area; print(bbox_to_firms_area())')" ...
    """
    b = bbox or DEMO_BBOX
    return f'{b["west"]},{b["south"]},{b["east"]},{b["north"]}'

# Standardized output schema for anomaly_features.csv — Squad 2 (AI) reads
# exactly these column names. Do not rename without updating the schema
# doc + notifying Integration Lead.
_BASE_SCHEMA_COLUMNS = [
    "anomaly_id",
    "latitude",
    "longitude",
    "nearest_industry",
    "nearest_industry_name",
    "distance_m",
    "land_cover",
    "nearest_forest_km",
]

OUTPUT_SCHEMA_COLUMNS = (
    _BASE_SCHEMA_COLUMNS + ["population_proximity"]
    if INCLUDE_POPULATION_PROXIMITY
    else _BASE_SCHEMA_COLUMNS
)
