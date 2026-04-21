"""Entry point for ``python -m aerobatic_kml``."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
