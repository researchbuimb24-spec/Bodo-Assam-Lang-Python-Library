"""Package main entry point for running python -m bhasha_lib."""

from __future__ import annotations

import sys

from bhasha_lib.cli import main

if __name__ == "__main__":
    sys.exit(main())
