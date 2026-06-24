#!/usr/bin/env python3
"""
Vendor all runtime wheels into ./wheels/ for a true air-gapped install (spec: no internet after
install). Run on a networked machine with the SAME OS + Python 3.11 as the target.

    python scripts/vendor_wheels.py [requirements.txt]

Then, on the offline target:
    pip install --no-index --find-links wheels -r requirements.txt
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    req = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "requirements.txt")
    dest = os.path.join(ROOT, "wheels")
    os.makedirs(dest, exist_ok=True)
    subprocess.check_call([sys.executable, "-m", "pip", "download", "-r", req, "-d", dest])
    print(f"wheels vendored to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
