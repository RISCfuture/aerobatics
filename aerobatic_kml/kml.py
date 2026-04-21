"""KML writer targeted at ForeFlight.

Emits canonical KML 2.2: one ``<Placemark>`` per ``<Polygon>``, and one
``<innerBoundaryIs>`` element per hole. (``simplekml`` produces a
non-standard form that wraps all holes in a single ``<innerBoundaryIs>``;
GDAL and ForeFlight silently under-read that.)
"""

from __future__ import annotations

import logging
from pathlib import Path

from .geometry import iter_polygons

LOG = logging.getLogger(__name__)


# KML colors are "aabbggrr". Outlines disabled: at continental scale they add
# thousands of near-pixel-wide edges that saturate mobile renderers without
# adding information. Fill alpha chosen so chart text/lines remain legible
# under a single layer but prohibition is unambiguous at a glance.
PROHIBITED_FILL_COLOR = "70C87832"   # alpha 0x70 (~44%) BGR C87832 (medium blue)
PROHIBITED_LINE_COLOR = "00000000"
PROHIBITED_LINE_WIDTH = 0

PERMITTED_FILL_COLOR = "5500A000"    # translucent green
PERMITTED_LINE_COLOR = "00000000"


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _coords_text(ring) -> str:
    """Format a shapely ring as KML coordinates (lon,lat,alt tuples)."""
    return " ".join(f"{c[0]:.6f},{c[1]:.6f},0" for c in ring.coords)


def write_kml(
    geom,
    out_path: Path,
    *,
    document_name: str,
    folder_name: str,
    fill_abgr: str,
    line_abgr: str,
    line_width: int,
) -> int:
    """Write a ForeFlight-friendly KML for a (Multi)Polygon geometry.

    Returns the number of Polygon placemarks written.
    """
    LOG.info("writing KML to %s", out_path)
    with open(out_path, "w", encoding="utf-8") as out:
        w = out.write
        w('<?xml version="1.0" encoding="UTF-8"?>\n')
        w('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
        w('  <Document>\n')
        w(f'    <name>{_xml_escape(document_name)}</name>\n')
        w('    <Style id="prohibited">\n')
        w('      <LineStyle>\n')
        w(f'        <color>{line_abgr}</color>\n')
        w(f'        <width>{line_width}</width>\n')
        w('      </LineStyle>\n')
        w('      <PolyStyle>\n')
        w(f'        <color>{fill_abgr}</color>\n')
        w('        <fill>1</fill>\n')
        w(f'        <outline>{1 if line_width > 0 else 0}</outline>\n')
        w('      </PolyStyle>\n')
        w('    </Style>\n')
        w('    <Folder>\n')
        w(f'      <name>{_xml_escape(folder_name)}</name>\n')

        count = 0
        for poly in iter_polygons(geom):
            w('      <Placemark>\n')
            w('        <styleUrl>#prohibited</styleUrl>\n')
            w('        <Polygon>\n')
            w('          <outerBoundaryIs><LinearRing><coordinates>')
            w(_coords_text(poly.exterior))
            w('</coordinates></LinearRing></outerBoundaryIs>\n')
            for hole in poly.interiors:
                w('          <innerBoundaryIs><LinearRing><coordinates>')
                w(_coords_text(hole))
                w('</coordinates></LinearRing></innerBoundaryIs>\n')
            w('        </Polygon>\n')
            w('      </Placemark>\n')
            count += 1

        w('    </Folder>\n')
        w('  </Document>\n')
        w('</kml>\n')

    LOG.info("wrote %d polygons", count)
    return count
