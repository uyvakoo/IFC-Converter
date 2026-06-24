#!/usr/bin/env python3
"""
Download the pinned native binaries into ./bin/ (idempotent).

These are intentionally NOT committed (see .gitignore) — they are large and have their own upstream
releases. CI and local developers run this once before building/testing. Air-gapped delivery bundles
them inside the PyInstaller artifact, not the repo.

    python scripts/fetch_binaries.py
"""
from __future__ import annotations

import os
import sys
import zipfile
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")

TARGETS = [
    {
        "name": "IfcConvert.exe",
        "url": "https://github.com/IfcOpenShell/IfcOpenShell/releases/download/"
               "ifcconvert-0.8.5/ifcconvert-0.8.5-win64.zip",
    },
    {
        "name": "gltfpack.exe",
        "url": "https://github.com/zeux/meshoptimizer/releases/download/v1.1/gltfpack-windows.zip",
    },
]


def fetch(target: dict) -> None:
    dest = os.path.join(BIN, target["name"])
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  exists: {target['name']}")
        return
    print(f"  downloading {target['name']} <- {target['url']}")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "asset.zip")
        urllib.request.urlretrieve(target["url"], zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            member = next(n for n in zf.namelist()
                          if os.path.basename(n).lower() == target["name"].lower())
            with zf.open(member) as src, open(dest, "wb") as out:
                out.write(src.read())
    print(f"  wrote {dest} ({os.path.getsize(dest):,} bytes)")


def main() -> int:
    os.makedirs(BIN, exist_ok=True)
    for target in TARGETS:
        fetch(target)
    print("binaries ready in bin/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
