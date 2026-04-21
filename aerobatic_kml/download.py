"""HTTP download with on-disk caching, plus a shapefile-in-zip reader."""

from __future__ import annotations

import logging
import urllib.parse
import zipfile
from pathlib import Path

import geopandas as gpd
import requests

from .config import HEADERS

LOG = logging.getLogger(__name__)


def _cache_name(url: str) -> str:
    """Build a filesystem-safe cache filename from a URL."""
    return urllib.parse.quote(url, safe="")[:240]


def download(url: str, cache_dir: Path) -> Path:
    """Download url to cache_dir (skipping if already present). Returns path."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / _cache_name(url)
    if out.exists() and out.stat().st_size > 0:
        return out
    LOG.info("downloading %s", url)
    with requests.get(url, stream=True, timeout=600, headers=HEADERS) as r:
        r.raise_for_status()
        tmp = out.with_suffix(out.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(out)
    return out


def load_zipped_shapefile(zip_path: Path) -> gpd.GeoDataFrame:
    """Read the first .shp inside a zip archive into a GeoDataFrame."""
    with zipfile.ZipFile(zip_path) as zf:
        shp = next(n for n in zf.namelist() if n.lower().endswith(".shp"))
    return gpd.read_file(f"zip://{zip_path}!{shp}")
