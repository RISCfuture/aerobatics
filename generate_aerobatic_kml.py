#!/usr/bin/env python3
"""
Entry point for the 91.303 Aerobatic Areas ForeFlight content pack builder.

Implementation lives in the ``aerobatic_kml`` package; this script is a
thin shim so the GitHub Actions workflow, README, and pyenv scripts can
continue to call a single file by name. Equivalent:

    python -m aerobatic_kml [flags]
"""
import sys

from aerobatic_kml.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
