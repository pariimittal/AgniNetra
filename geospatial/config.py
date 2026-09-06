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

# Standardized output schema for anomaly_features.csv — Squad 2 (AI) reads
# exactly these column names. Do not rename without updating the schema
# doc + notifying Integration Lead.
OUTPUT_SCHEMA_COLUMNS = [
    "anomaly_id",
    "latitude",
    "longitude",
    "nearest_industry",
    "nearest_industry_name",
    "distance_m",
    "land_cover",
    "nearest_forest_km",
    "population_proximity",
]
