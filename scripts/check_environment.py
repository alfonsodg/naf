#!/usr/bin/env python3
"""Validate that required environment variables are present.

Prints the names of missing variables and exits non-zero. Values are never
printed, so the script is safe to run in CI logs.
"""

import os
import sys

REQUIRED = (
    "NAF_DATABASE_URL",
    "NAF_MINIFLUX_URL",
    "NAF_MINIFLUX_API_KEY",
)


def main() -> int:
    """Report missing required variables by name only."""
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        print("missing required configuration: " + ", ".join(missing))
        return 1
    print("configuration: all required variables present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
