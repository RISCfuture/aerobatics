"""FAA NASR cycle discovery and CSV-inside-zip reading."""

from __future__ import annotations

import datetime as _dt
import logging
import re
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from .config import HEADERS

LOG = logging.getLogger(__name__)


def discover_nasr_cycle(landing_url: str) -> tuple[str, str]:
    """
    Return (effective_date, cycle_dir_url) for the most recent NASR cycle
    whose download page is already published.

      effective_date: "YYYY-MM-DD"
      cycle_dir_url:  base URL of the per-cycle directory on nfdc.faa.gov
    """
    r = requests.get(landing_url, timeout=60, headers=HEADERS)
    r.raise_for_status()
    # e.g. "./../NASR_Subscription/2026-04-16"
    dates = sorted(set(re.findall(
        r'NASR_Subscription/(\d{4}-\d{2}-\d{2})', r.text
    )))
    if not dates:
        raise RuntimeError(f"no cycle dates found at {landing_url}")
    # Pick the newest date whose detail page actually lists downloads.
    for date in reversed(dates):
        detail_url = landing_url.rstrip("/") + f"/{date}"
        r2 = requests.get(detail_url, timeout=60, headers=HEADERS)
        if r2.status_code != 200:
            continue
        if "class_airspace_shape_files.zip" not in r2.text:
            continue
        cycle_dir = f"https://nfdc.faa.gov/webContent/28DaySub/{date}/"
        LOG.info("NASR cycle resolved: %s", date)
        return date, cycle_dir
    raise RuntimeError("no NASR cycle page with download links was found")


def csv_group_url(cycle_date: str, group: str) -> str:
    """URL for a single-group NASR CSV zip (e.g. AWY, FIX, NAV).

    FAA uses DD_MONSHORT_YYYY in the filename, e.g. '16_Apr_2026'.
    """
    d = _dt.datetime.strptime(cycle_date, "%Y-%m-%d")
    tag = d.strftime("%d_%b_%Y")
    return (
        f"https://nfdc.faa.gov/webContent/28DaySub/extra/"
        f"{tag}_{group}_CSV.zip"
    )


def read_csv_from_zip(zip_path: Path, name_patterns: Iterable[str]) -> pd.DataFrame:
    """Read a NASR CSV by matching any of the given filename patterns."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        candidates = [
            n for n in names
            if any(p.upper() in n.upper() for p in name_patterns)
            and n.lower().endswith(".csv")
        ]
        if not candidates:
            raise RuntimeError(
                f"no NASR CSV matching {list(name_patterns)} in {zip_path}"
            )
        with zf.open(candidates[0]) as f:
            return pd.read_csv(f, dtype=str, low_memory=False)
