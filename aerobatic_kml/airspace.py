"""FAA Class Airspace loader for 91.303(c), filtered per the Hucker letter.

Hucker interpretation (2006, Rebecca MacPherson, FAA Chief Counsel;
https://www.faa.gov/media/15186): "surface areas" in 91.303(c) refers only
to airspace that actually touches the surface of the earth.

  * Class B / Class C inner cores (LOWER_CODE=SFC) - the outer shelves of
    the "upside-down wedding cake" are NOT surface areas, and aerobatics
    ARE permitted there (subject to 91.130 / 91.131 and 91.303(a,b,d,e,f)).
  * Class D - included only when the floor begins at the surface.
  * Class E - included only for E2 ("surface area designated for an
    airport"). E3 (Class-D extensions), E4 (Class-B/C extensions), E5
    (domestic en-route), E6 (offshore), and E7 (Alaska uncontrolled) are
    not designated for an airport and are excluded.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .config import WGS84
from .download import download

LOG = logging.getLogger(__name__)


def load_airport_airspace(cache: Path, cycle_dir_url: str) -> gpd.GeoDataFrame:
    """Return Class B/C/D/E2 airspace features in WGS84 per Hucker-2006.

    The returned GeoDataFrame has one row per retained FAA feature, plus an
    extra column `_CLASS` holding the normalized class code.
    """
    zip_url = cycle_dir_url.rstrip("/") + "/class_airspace_shape_files.zip"
    LOG.info("loading FAA Class Airspace shapefile: %s", zip_url)
    zip_path = download(zip_url, cache)

    with zipfile.ZipFile(zip_path) as zf:
        shps = [n for n in zf.namelist() if n.lower().endswith(".shp")]
    if not shps:
        raise RuntimeError(f"no .shp in {zip_path}")

    frames = []
    for shp in shps:
        LOG.info("  reading %s", shp)
        frames.append(gpd.read_file(f"zip://{zip_path}!{shp}"))
    gdf = pd.concat(frames, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=frames[0].crs)
    gdf = gdf.to_crs(WGS84)
    # Uppercase attribute columns but preserve the active geometry binding.
    rename = {c: c.upper() for c in gdf.columns if c != gdf.geometry.name}
    gdf = gdf.rename(columns=rename)

    # Class code is usually in CLASS (one of 'B', 'C', 'D', 'E').
    cls_col = next(
        (c for c in ("CLASS", "CLASS_CODE", "TYPE_CODE", "LOCAL_TYPE")
         if c in gdf.columns),
        None,
    )
    if cls_col is None:
        raise RuntimeError(
            f"no class-code column in {list(gdf.columns)[:30]}..."
        )
    gdf["_CLASS"] = gdf[cls_col].astype(str).str.strip().str.upper()

    # LOWER_CODE == 'SFC' means the feature reaches the surface (the Hucker
    # gate). For Class E we additionally require LOCAL_TYPE == 'CLASS_E2'.
    sfc = gdf.get("LOWER_CODE", pd.Series([""] * len(gdf))) \
        .astype(str).str.upper().eq("SFC")
    local_type = gdf.get("LOCAL_TYPE", pd.Series([""] * len(gdf))) \
        .astype(str).str.upper()

    is_bcd = gdf["_CLASS"].isin({"B", "C", "D"}) & sfc
    is_e2 = (gdf["_CLASS"] == "E") & sfc & (local_type == "CLASS_E2")
    keep = is_bcd | is_e2

    by_class = {
        "B":  int((keep & (gdf["_CLASS"] == "B")).sum()),
        "C":  int((keep & (gdf["_CLASS"] == "C")).sum()),
        "D":  int((keep & (gdf["_CLASS"] == "D")).sum()),
        "E2": int(is_e2.sum()),
    }
    LOG.info(
        "class airspace: %d total, keeping %d (per Hucker 2006): %s",
        len(gdf), int(keep.sum()), by_class,
    )
    return gdf.loc[keep].reset_index(drop=True)
