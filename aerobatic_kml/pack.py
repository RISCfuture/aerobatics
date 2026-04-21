"""Assemble a ForeFlight content pack (.zip) from a KML and metadata.

Layout inside the zip:

    <pack_root>/
        manifest.json
        layers/
            <kml_filename>

See https://foreflight.com/support/content-packs/ for the spec.

The NASR 28-day cycle is aligned with the global AIRAC cycle, so the
cycle_date argument doubles as the AIRAC effective date.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import zipfile
from pathlib import Path

LOG = logging.getLogger(__name__)


def build_foreflight_pack(
    out_zip: Path,
    kml_path: Path,
    *,
    cycle_date: str,
    pack_name: str,
    pack_abbrev: str,
    organization: str,
) -> None:
    effective = _dt.datetime.strptime(cycle_date, "%Y-%m-%d")
    expires = effective + _dt.timedelta(days=28)

    # Readable integer version: YYYYMMDD.
    version = int(effective.strftime("%Y%m%d"))

    manifest = {
        "name": pack_name,
        "abbreviation": pack_abbrev,
        "version": version,
        "effectiveDate": effective.strftime("%Y%m%dT00:00:00Z"),
        "expirationDate": expires.strftime("%Y%m%dT00:00:00Z"),
        "organizationName": organization,
    }
    pack_root = pack_name  # readable folder name inside the zip
    LOG.info("building ForeFlight pack %s (root=%s)", out_zip, pack_root)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            f"{pack_root}/manifest.json",
            json.dumps(manifest, indent=2) + "\n",
        )
        z.write(kml_path, f"{pack_root}/layers/{kml_path.name}")
    LOG.info("pack written: %s (%.1f MB)",
             out_zip, out_zip.stat().st_size / 1024 / 1024)
