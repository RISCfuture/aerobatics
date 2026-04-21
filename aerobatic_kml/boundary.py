"""Loaders for U.S. land boundary and Census urban areas (91.303(a) proxy)."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .config import WGS84
from .download import download, load_zipped_shapefile

LOG = logging.getLogger(__name__)


def load_us_boundary(cache: Path, url: str) -> gpd.GeoDataFrame:
    """Return the U.S. land-area features in WGS84 (not clipped, not dissolved)."""
    LOG.info("loading U.S. national boundary")
    path = download(url, cache)
    return load_zipped_shapefile(path).to_crs(WGS84)


def load_urban_areas(cache: Path, url: str) -> gpd.GeoDataFrame:
    """Return all U.S. Census urban-area features in WGS84.

    Used as the public proxy for "congested area" in 91.303(a).
    """
    LOG.info("loading Census urban areas (congested-area proxy)")
    path = download(url, cache)
    return load_zipped_shapefile(path).to_crs(WGS84)
