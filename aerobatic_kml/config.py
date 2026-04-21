"""Constants, CRS region table, and URL defaults."""

from __future__ import annotations

import dataclasses


# --- Units / CRS --------------------------------------------------------------

NM_TO_METERS = 1852.0
AIRWAY_BUFFER_NM = 4.0
AIRWAY_BUFFER_M = AIRWAY_BUFFER_NM * NM_TO_METERS

WGS84 = "EPSG:4326"


# --- Per-region processing ----------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Region:
    """A U.S. jurisdiction processed in its own metric CRS.

    EPSG:5070 only round-trips cleanly within CONUS. Points outside CONUS
    produce antimeridian-wrapping artifacts when reprojected back to WGS84,
    which KML renderers draw as globe-spanning polygons. Each non-CONUS
    region is therefore processed in a CRS appropriate for its geography.
    """

    key: str
    name: str
    crs: str
    # (lon_min, lat_min, lon_max, lat_max) in WGS84 degrees. All bboxes are
    # strictly on one side of the antimeridian.
    clip_bbox: tuple[float, float, float, float]


REGIONS: tuple[Region, ...] = (
    Region("conus", "Contiguous 48 States",
           "EPSG:5070",  (-130.0,  22.0,  -64.0, 50.0)),
    Region("ak",    "Alaska",
           "EPSG:3338",  (-180.0,  50.0, -129.0, 72.0)),
    Region("hi",    "Hawaii",
           "EPSG:32604", (-162.0,  18.0, -154.0, 23.0)),
    Region("pr_vi", "Puerto Rico and U.S. Virgin Islands",
           "EPSG:32161", ( -68.0,  17.0,  -64.0, 19.0)),
    Region("samoa", "American Samoa",
           "EPSG:32702", (-173.0, -15.0, -168.0, -13.0)),
    Region("guam_cnmi", "Guam and Northern Mariana Islands",
           "EPSG:32655", ( 144.0,  13.0,  146.5, 21.0)),
)


# --- Source data URLs ---------------------------------------------------------

DEFAULTS: dict[str, str] = {
    # U.S. nation cartographic boundary (5M = 1:5,000,000 generalized)
    "nation_url": (
        "https://www2.census.gov/geo/tiger/GENZ2023/shp/"
        "cb_2023_us_nation_5m.zip"
    ),
    # 2020 Census Urban Areas (proxy for "congested area")
    "urban_url": (
        "https://www2.census.gov/geo/tiger/TIGER2024/UAC20/"
        "tl_2024_us_uac20.zip"
    ),
    # FAA NASR subscription landing page; we scrape for the latest cycle.
    "nasr_landing": (
        "https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/"
        "NASR_Subscription/"
    ),
}

# Standard User-Agent; some FAA/CDN endpoints 403/503 on default Python UA.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA}


# --- Pack metadata (user-visible branding) ------------------------------------

PACK_NAME = "91.303 Aerobatic Areas"
PACK_ABBREV = "91.303"
ORGANIZATION = "Tim Morgan"
KML_FILENAME = "91.303 Prohibited Areas.kml"
