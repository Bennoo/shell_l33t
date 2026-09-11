#!/usr/bin/env python3
"""Shim so `python3 game.py` keeps working. Real code lives in the l33t package."""

import sys

from l33t.cli import main

if __name__ == "__main__":
    sys.exit(main())
