# 91.303 Aerobatic Areas — ForeFlight content pack

A ForeFlight content pack that shades the areas of the United States where
aerobatic flight is prohibited under [14 CFR 91.303][reg], so the unshaded
regions are (laterally) available for Part-91 aerobatic practice.

[reg]: https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-91/subpart-B/subject-group-ECFRac298ad55f4b0ed/section-91.303

## Install into ForeFlight

Each NASR/AIRAC cycle produces a tagged release on this repo. On the iOS
device that has ForeFlight installed:

1. Open the [latest release][latest] in Safari.
2. Tap the **Install in ForeFlight** link.
3. When the preview appears, long-press or pull the page down and tap
   **Open in ForeFlight**.

The pack downloads into **More → Downloads** and the shaded layer turns on
under **Maps → Layers**.

[latest]: ../../releases/latest

## What the layer shows

Translucent blue polygons cover every area where **at least one** of
14 CFR 91.303's lateral restrictions applies:

- **91.303(a)** Congested areas of a city, town, or settlement, approximated
  by U.S. Census Bureau 2020 Urban Areas (the most widely-used public proxy
  for the yellow-tinted "city" areas on sectional charts).
- **91.303(c)** Within the lateral boundaries of the surface areas of
  Class B, C, D, or E airspace designated for an airport. Filtered per the
  FAA Chief Counsel's [Hucker interpretation (2006)][hucker]: only the
  inner-core ring of Class B and C (the component that actually touches the
  surface); all Class D; Class E only where `LOCAL_TYPE = CLASS_E2`. Outer
  Class B/C shelves are **not** surface areas and aerobatic flight is
  permitted there (subject to ATC clearance under 91.131 / 91.130 and the
  other 91.303 sub-paragraphs).
- **91.303(d)** Within 4 NM of the centerline of any Federal airway.
  Filtered to U.S. domestic Victor (V) routes and colored Federal airways
  (BF / G / R / PR). Q- and T-routes (published as RNAV routes in FAA
  Order 7400.11, not as airways under 14 CFR Part 71) are excluded, as are
  North Atlantic (AT) and Pacific (PA) oceanic routes and J-routes (high
  altitude, beyond the practical reach of Part-91 aerobatic flight).

**Not** represented:

- 91.303(b) open-air assemblies — ephemeral, no authoritative dataset.
- Any altitude or vertical restriction.
- Visibility / weather conditions.

[hucker]: https://www.faa.gov/media/15186

Scope: CONUS, Alaska, Hawaii, Puerto Rico and USVI, American Samoa, and
Guam/CNMI. The Aleutian chain past +180° (Attu and nearby) is excluded.

This pack is an educational aid, **not** a legal flight-planning tool.
Always consult current FAA publications and an authoritative chart before
conducting aerobatic flight.

## Build locally

```
pyenv virtualenv 3.11.14 aerobatics
pyenv activate aerobatics
pip install -r requirements.txt
python generate_aerobatic_kml.py -v
```

Output: `91.303 Aerobatic Areas.zip` in the working directory. Downloads
(~100 MB) are cached under `data_cache/`.

Useful flags:

| flag | effect |
|---|---|
| `--kml-only` | write just the styled KML, skip the pack wrapper |
| `--show permitted` | render the permitted layer instead of prohibited |
| `--regions conus,hi` | only process the listed regions |
| `--nasr-cycle 2026-04-16` | pin an older cycle instead of auto-discovering |
| `--simplify 0.01 --min-area-km2 5` | more aggressive simplification for mobile |
| `--print-cycle` | resolve and print the current NASR cycle, then exit |

## Source layout

The code is split into small, focused modules under `aerobatic_kml/`:

| module | concern |
|---|---|
| `config` | CRS/region table, URL defaults, pack metadata |
| `download` | HTTP + on-disk caching, zipped-shapefile reader |
| `nasr` | FAA NASR cycle discovery, CSV extraction |
| `boundary` | TIGER nation polygon, Census urban areas |
| `airspace` | FAA Class Airspace loader + Hucker-2006 filter |
| `airways` | NASR Federal-airway loader + Part-71 designation filter |
| `geometry` | per-region compute and cross-region merge |
| `kml` | ForeFlight-friendly KML writer |
| `pack` | content-pack (`manifest.json` + `layers/`) assembler |
| `cli` | argparse entry point |

## Data sources

- [FAA NASR Subscription](https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/)
  (airways, fixes, navaids, Class Airspace shapefile).
- [U.S. Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)
  2024 Urban Areas and 2023 cartographic boundary for the nation.
- [FAA Chief Counsel Hucker letter (2006)](https://www.faa.gov/media/15186)
  for the interpretation of "surface areas" in 91.303(c).
