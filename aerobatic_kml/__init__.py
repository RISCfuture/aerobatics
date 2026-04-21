"""
Generate a ForeFlight content pack shading the areas of the United States
where 14 CFR 91.303 prohibits aerobatic flight.

Submodules:

    config      Constants, REGIONS table, URL defaults, pack metadata.
    download    HTTP + on-disk caching of source datasets.
    nasr        FAA NASR cycle discovery and CSV extraction helpers.
    boundary    U.S. land / Census urban-area loaders.
    airspace    FAA Class Airspace loader + Hucker-2006 filter.
    airways     NASR Federal-airway loader + Part-71 designation filter.
    geometry    Per-region compute + cross-region merge pipeline.
    kml         ForeFlight-friendly KML writer.
    pack        ForeFlight content-pack (manifest.json + layers/) assembler.
    cli         argparse entry point; also exported as ``python -m aerobatic_kml``.

The file-level script ``generate_aerobatic_kml.py`` is a thin wrapper that
calls :func:`aerobatic_kml.cli.main`.
"""
