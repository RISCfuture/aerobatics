"""Command-line entry point: parse args, orchestrate build, emit pack/KML."""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from .airspace import load_airport_airspace
from .airways import load_federal_airways
from .boundary import load_urban_areas, load_us_boundary
from .config import (
    DEFAULTS,
    KML_FILENAME,
    ORGANIZATION,
    PACK_ABBREV,
    PACK_NAME,
    REGIONS,
)
from .geometry import compute_prohibited_and_permitted
from .kml import (
    PERMITTED_FILL_COLOR,
    PERMITTED_LINE_COLOR,
    PROHIBITED_FILL_COLOR,
    PROHIBITED_LINE_COLOR,
    PROHIBITED_LINE_WIDTH,
    write_kml,
)
from .nasr import discover_nasr_cycle
from .pack import build_foreflight_pack


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(f"{PACK_NAME}.zip"),
        help="Output ForeFlight content pack (.zip). "
        "If --kml-only is set, this is the KML path instead.",
    )
    ap.add_argument(
        "--kml-only",
        action="store_true",
        help="Write just the KML, not a ForeFlight content pack.",
    )
    ap.add_argument(
        "--show",
        choices=("prohibited", "permitted"),
        default="prohibited",
        help="Which region to shade in the KML. 'prohibited' (the default) "
        "renders areas where aerobatic flight is NOT permitted - this is the "
        "layer most useful as a ForeFlight overlay.",
    )
    ap.add_argument("--cache", type=Path, default=Path("data_cache"))
    ap.add_argument(
        "--simplify",
        type=float,
        default=0.005,
        help="Douglas-Peucker tolerance in degrees (~550m at 5e-3). "
        "Larger = fewer vertices, much faster on mobile. 0 disables.",
    )
    ap.add_argument(
        "--min-area-km2",
        type=float,
        default=2.0,
        help="Drop prohibited islands and permitted holes smaller than this "
        "(km²). 0 to keep everything. Default 2 km² (~0.75 sq mi) culls "
        "slivers that roughly double rendering cost for no visible gain.",
    )
    ap.add_argument("--nation-url", default=DEFAULTS["nation_url"])
    ap.add_argument("--urban-url", default=DEFAULTS["urban_url"])
    ap.add_argument("--nasr-landing", default=DEFAULTS["nasr_landing"])
    ap.add_argument(
        "--nasr-cycle",
        default=None,
        help="NASR cycle effective date YYYY-MM-DD. If omitted, auto-discovered.",
    )
    ap.add_argument(
        "--nasr-zip",
        default=None,
        help="Path to a manually-downloaded NASR full-subscription CSV zip. "
        "If provided, used in place of the per-group AWY/FIX/NAV downloads.",
    )
    ap.add_argument(
        "--regions",
        default=None,
        help="Comma-separated list of region keys to process. "
        f"Available: {','.join(r.key for r in REGIONS)}. Default: all regions.",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument(
        "--print-cycle",
        action="store_true",
        help="Resolve the current NASR cycle date and print it to stdout, "
        "then exit without building anything. Used by CI to tag releases.",
    )
    return ap


def main(argv: list[str]) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cache: Path = args.cache
    cache.mkdir(parents=True, exist_ok=True)

    if args.nasr_cycle:
        cycle_date = args.nasr_cycle
        cycle_dir = f"https://nfdc.faa.gov/webContent/28DaySub/{cycle_date}/"
    else:
        cycle_date, cycle_dir = discover_nasr_cycle(args.nasr_landing)

    if args.print_cycle:
        print(cycle_date)
        return 0

    us = load_us_boundary(cache, args.nation_url)
    urban = load_urban_areas(cache, args.urban_url)
    airspace = load_airport_airspace(cache, cycle_dir)
    airways = load_federal_airways(cache, cycle_date, args.nasr_zip)

    if args.regions:
        wanted = {k.strip() for k in args.regions.split(",") if k.strip()}
        unknown = wanted - {r.key for r in REGIONS}
        if unknown:
            ap.error(f"unknown region(s): {sorted(unknown)}. "
                     f"Available: {[r.key for r in REGIONS]}")
        selected = tuple(r for r in REGIONS if r.key in wanted)
    else:
        selected = REGIONS

    prohibited, permitted = compute_prohibited_and_permitted(
        us, urban, airspace, airways,
        simplify_deg=args.simplify,
        min_feature_area_m2=args.min_area_km2 * 1e6,
        regions=selected,
    )
    geom = prohibited if args.show == "prohibited" else permitted

    if args.show == "prohibited":
        doc_name = "91.303 Prohibited Areas"
        folder = "Prohibited"
        fill = PROHIBITED_FILL_COLOR
        line = PROHIBITED_LINE_COLOR
    else:
        doc_name = "91.303 Permitted Areas"
        folder = "Permitted"
        fill = PERMITTED_FILL_COLOR
        line = PERMITTED_LINE_COLOR

    if args.kml_only:
        kml_path = args.out
        write_kml(
            geom, kml_path,
            document_name=doc_name,
            folder_name=folder,
            fill_abgr=fill,
            line_abgr=line,
            line_width=PROHIBITED_LINE_WIDTH,
        )
        print(f"wrote {kml_path}")
        return 0

    # ForeFlight content pack flow: write KML to a temp location, then wrap.
    with tempfile.TemporaryDirectory() as td:
        kml_tmp = Path(td) / KML_FILENAME
        write_kml(
            geom, kml_tmp,
            document_name=doc_name,
            folder_name=folder,
            fill_abgr=fill,
            line_abgr=line,
            line_width=PROHIBITED_LINE_WIDTH,
        )
        build_foreflight_pack(
            args.out, kml_tmp,
            cycle_date=cycle_date,
            pack_name=PACK_NAME,
            pack_abbrev=PACK_ABBREV,
            organization=ORGANIZATION,
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
