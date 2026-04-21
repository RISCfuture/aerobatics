"""Federal-airway loader for 91.303(d), filtered by Part-71 designation.

14 CFR Part 71 designates Victor airways (V-) and colored Federal airways
(Blue / Green / Red / Puerto Rico) as "Federal airways." Q- and T-routes
are published in FAA Order 7400.11 as "RNAV routes," not airways, and do
not carry the 91.303(d) 4-NM buffer. North Atlantic (AT) and Pacific (PA)
oceanic routes are not U.S. domestic Federal airways either. J-routes are
Federal airways but only above FL180, which is outside the practical
range of Part-91 aerobatic flight, so we exclude them too.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from .config import WGS84
from .download import download
from .nasr import csv_group_url, read_csv_from_zip

LOG = logging.getLogger(__name__)


# AWY_DESIGNATION values in NASR AWY_BASE:
#
#   V    VOR Federal airways (low altitude)     - KEEP
#   BF   Blue colored Federal airways           - KEEP
#   G    Green colored Federal airways          - KEEP
#   R    Red colored Federal airways            - KEEP
#   PR   Colored Federal airways (Puerto Rico)  - KEEP
#   J    Jet routes (FL180+)                    - EXCLUDE (above aerobatic range)
#   RN   RNAV routes (Q and T)                  - EXCLUDE (not Part-71 airways)
#   AT   North Atlantic oceanic routes          - EXCLUDE (not domestic Federal)
#   PA   Pacific oceanic routes                 - EXCLUDE (not domestic Federal)
EXCLUDED_AIRWAY_DESIGNATIONS = frozenset({"J", "RN", "AT", "PA"})


def load_federal_airways(
    cache: Path,
    cycle_date: str,
    nasr_zip_override: str | None,
) -> gpd.GeoDataFrame:
    """
    Build WGS84 LineStrings for every federal low-altitude airway leg, by
    joining AWY_SEG_ALT with FIX_BASE / NAV_BASE. One row per leg.

    Buffering at 4 NM is deferred to the per-region pipeline so each region
    can buffer in its own metric CRS.
    """
    if nasr_zip_override:
        # Single zip covers all NASR groups.
        awy_zip = fix_zip = nav_zip = Path(nasr_zip_override)
        if not awy_zip.exists():
            raise FileNotFoundError(awy_zip)
    else:
        awy_zip = download(csv_group_url(cycle_date, "AWY"), cache)
        fix_zip = download(csv_group_url(cycle_date, "FIX"), cache)
        nav_zip = download(csv_group_url(cycle_date, "NAV"), cache)

    LOG.info("parsing NASR: airways + fixes + navaids")
    seg = read_csv_from_zip(awy_zip, ["AWY_SEG_ALT", "AWY_SEG"])
    base = read_csv_from_zip(awy_zip, ["AWY_BASE"])
    fix = read_csv_from_zip(fix_zip, ["FIX_BASE"])
    nav = read_csv_from_zip(nav_zip, ["NAV_BASE"])

    for df in (seg, base, fix, nav):
        df.columns = [c.upper() for c in df.columns]

    # AWY_SEG_ALT has only AWY_ID; the type lives in AWY_BASE.AWY_DESIGNATION.
    # Join on (AWY_ID, AWY_LOCATION) because the same AWY_ID can appear in
    # multiple locales.
    join_keys = [c for c in ("AWY_ID", "AWY_LOCATION") if c in base.columns]
    designations = base[join_keys + ["AWY_DESIGNATION"]].drop_duplicates()
    before = len(seg)
    seg = seg.merge(designations, on=join_keys, how="left")
    seg["AWY_DESIGNATION"] = seg["AWY_DESIGNATION"].fillna("").str.upper()
    seg = seg[~seg["AWY_DESIGNATION"].isin(EXCLUDED_AIRWAY_DESIGNATIONS)].copy()
    by_desig = seg["AWY_DESIGNATION"].value_counts().to_dict()
    LOG.info(
        "airway segments: %d -> %d after excluding designations %s; kept: %s",
        before, len(seg),
        sorted(EXCLUDED_AIRWAY_DESIGNATIONS), by_desig,
    )

    def _coord_dict(df: pd.DataFrame, id_col: str) -> dict:
        sub = df[[id_col, "LAT_DECIMAL", "LONG_DECIMAL"]].copy()
        sub["LAT_DECIMAL"] = pd.to_numeric(sub["LAT_DECIMAL"], errors="coerce")
        sub["LONG_DECIMAL"] = pd.to_numeric(sub["LONG_DECIMAL"], errors="coerce")
        sub = sub.dropna()
        return dict(zip(sub[id_col], zip(sub["LONG_DECIMAL"], sub["LAT_DECIMAL"])))

    fix_map = _coord_dict(fix, "FIX_ID")
    nav_map = _coord_dict(nav, "NAV_ID")
    # Fixes take precedence over navaids for name collisions.
    coord_map = {**nav_map, **fix_map}
    LOG.info("fix coords: %d, nav coords: %d, merged: %d",
             len(fix_map), len(nav_map), len(coord_map))

    from_col = "FROM_POINT" if "FROM_POINT" in seg.columns else "FROM_POINT_ID"
    to_col = "TO_POINT" if "TO_POINT" in seg.columns else "TO_POINT_ID"

    lines: list[LineString] = []
    missing = 0
    for frm, to in zip(seg[from_col], seg[to_col]):
        a = coord_map.get(frm)
        b = coord_map.get(to)
        if a and b:
            lines.append(LineString([a, b]))
        else:
            missing += 1

    LOG.info("built %d airway legs (%d skipped: unresolved endpoints)",
             len(lines), missing)
    if not lines:
        raise RuntimeError(
            "could not assemble any airway centerlines from NASR."
        )

    return gpd.GeoDataFrame(geometry=lines, crs=WGS84)
