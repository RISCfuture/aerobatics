"""Per-region geometry pipeline + cross-region merge."""

from __future__ import annotations

import logging
from typing import Iterable

import geopandas as gpd
from shapely import make_valid
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry import box as _box
from shapely.ops import unary_union

from .config import AIRWAY_BUFFER_M, REGIONS, Region, WGS84

LOG = logging.getLogger(__name__)


# --- Polygon iteration / sliver culling ---------------------------------------


def iter_polygons(geom) -> Iterable[Polygon]:
    """Yield every Polygon component of a (possibly nested) shapely geometry."""
    if geom.is_empty:
        return
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        for p in geom.geoms:
            yield p
    elif hasattr(geom, "geoms"):
        for g in geom.geoms:
            yield from iter_polygons(g)


def drop_small_parts(geom, min_area_m2: float):
    """Drop polygons and interior rings smaller than min_area_m2.

    Areas are measured in the geometry's own CRS (meters² in our pipeline),
    so the threshold is a direct area floor. Removes slivers and pinholes
    that blow up polygon count on mobile renderers.
    """
    if geom.is_empty:
        return geom
    parts = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    kept = []
    for p in parts:
        if p.area < min_area_m2:
            continue
        holes = [h for h in p.interiors
                 if Polygon(h).area >= min_area_m2]
        if holes or p.interiors:
            p = Polygon(p.exterior.coords, [h.coords for h in holes])
        kept.append(p)
    if not kept:
        return geom.__class__()
    return kept[0] if len(kept) == 1 else MultiPolygon(kept)


# --- Regional clipping helpers ------------------------------------------------


def clip_to_bbox(gdf: gpd.GeoDataFrame, bbox) -> gpd.GeoDataFrame:
    """Keep features whose bbox lies entirely within the given WGS84 bbox.

    "Entirely inside" is the right semantic for features that are small
    relative to the region (airspace cylinders, urban patches, airway legs);
    features that straddle the boundary belong to another region.
    """
    lon_lo, lat_lo, lon_hi, lat_hi = bbox

    def keep(g):
        xmin, ymin, xmax, ymax = g.bounds
        return (xmin >= lon_lo and xmax <= lon_hi
                and ymin >= lat_lo and ymax <= lat_hi)

    return gdf[gdf.geometry.apply(keep)]


def intersect_to_bbox(gdf: gpd.GeoDataFrame, bbox) -> gpd.GeoDataFrame:
    """Intersect each feature's geometry with the bbox; drop empties.

    Use this for coarse features that span multiple regions (e.g. the
    TIGER nation polygon). For small per-feature geometry, use
    :func:`clip_to_bbox` instead.
    """
    clip = _box(*bbox)
    out = gdf.copy()
    out["geometry"] = out.geometry.intersection(clip)
    return out[~out.geometry.is_empty]


# --- Per-region pipeline ------------------------------------------------------


def compute_region(
    region: Region,
    us_gdf: gpd.GeoDataFrame,
    urban_gdf: gpd.GeoDataFrame,
    airspace_gdf: gpd.GeoDataFrame,
    airway_legs_gdf: gpd.GeoDataFrame,
    simplify_m: float,
    min_feature_area_m2: float,
):
    """Compute (prohibited, permitted) WGS84 geometries for one region.

    Returns ``(prohibited_wgs, permitted_wgs)`` or ``None`` if the region
    has no input features.
    """
    us_r = intersect_to_bbox(us_gdf, region.clip_bbox)
    urban_r = clip_to_bbox(urban_gdf, region.clip_bbox)
    airspace_r = clip_to_bbox(airspace_gdf, region.clip_bbox)
    legs_r = clip_to_bbox(airway_legs_gdf, region.clip_bbox)

    if us_r.empty and airspace_r.empty and urban_r.empty and legs_r.empty:
        LOG.info("%s: no input features in clip bbox - skipping", region.key)
        return None

    LOG.info("%s: features clipped (us=%d urban=%d airspace=%d airways=%d)",
             region.key, len(us_r), len(urban_r), len(airspace_r), len(legs_r))

    def _union_proj(gdf):
        if gdf.empty:
            return None
        return make_valid(unary_union(gdf.to_crs(region.crs).geometry))

    us_m = _union_proj(us_r)
    urban_m = _union_proj(urban_r)
    airspace_m = _union_proj(airspace_r)

    airways_m = None
    if not legs_r.empty:
        buffered = legs_r.to_crs(region.crs).buffer(AIRWAY_BUFFER_M)
        airways_m = make_valid(unary_union(buffered))

    prohibited_parts = [g for g in (urban_m, airspace_m, airways_m) if g is not None]
    prohibited_m = unary_union(prohibited_parts) if prohibited_parts else None

    if us_m is not None and prohibited_m is not None:
        permitted_m = us_m.difference(prohibited_m)
    elif us_m is not None:
        permitted_m = us_m
    else:
        permitted_m = None

    if simplify_m > 0:
        if prohibited_m is not None:
            prohibited_m = make_valid(
                prohibited_m.simplify(simplify_m, preserve_topology=True))
        if permitted_m is not None:
            permitted_m = make_valid(
                permitted_m.simplify(simplify_m, preserve_topology=True))

    if min_feature_area_m2 > 0:
        if prohibited_m is not None:
            prohibited_m = drop_small_parts(prohibited_m, min_feature_area_m2)
        if permitted_m is not None:
            permitted_m = drop_small_parts(permitted_m, min_feature_area_m2)

    def _to_wgs(g):
        if g is None or g.is_empty:
            return None
        return gpd.GeoSeries([g], crs=region.crs).to_crs(WGS84).iloc[0]

    return _to_wgs(prohibited_m), _to_wgs(permitted_m)


def compute_prohibited_and_permitted(
    us: gpd.GeoDataFrame,
    urban: gpd.GeoDataFrame,
    airspace: gpd.GeoDataFrame,
    airways: gpd.GeoDataFrame,
    simplify_deg: float,
    min_feature_area_m2: float = 0.0,
    regions: tuple[Region, ...] = REGIONS,
):
    """Iterate regions, union results in WGS84. See :func:`compute_region`."""
    tol_m = simplify_deg * 111_111 if simplify_deg > 0 else 0.0
    if tol_m:
        LOG.info("simplify tolerance: %.0f m (%g deg)", tol_m, simplify_deg)

    prohibited_parts, permitted_parts = [], []
    for r in regions:
        LOG.info("--- region: %s (%s) ---", r.key, r.name)
        result = compute_region(
            r, us, urban, airspace, airways,
            simplify_m=tol_m,
            min_feature_area_m2=min_feature_area_m2,
        )
        if result is None:
            continue
        p, q = result
        if p is not None and not p.is_empty:
            prohibited_parts.append(p)
        if q is not None and not q.is_empty:
            permitted_parts.append(q)

    prohibited = (
        make_valid(unary_union([make_valid(g) for g in prohibited_parts]))
        if prohibited_parts else Polygon()
    )
    permitted = (
        make_valid(unary_union([make_valid(g) for g in permitted_parts]))
        if permitted_parts else Polygon()
    )

    n_prohibited = sum(1 for _ in iter_polygons(prohibited))
    n_permitted = sum(1 for _ in iter_polygons(permitted))
    LOG.info("merged: prohibited polys=%d, permitted polys=%d",
             n_prohibited, n_permitted)

    return prohibited, permitted
