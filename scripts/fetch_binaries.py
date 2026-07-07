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
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")

# Draco compression (optional, fetched with --with-draco) needs a Node runtime + gltf-pipeline.
NODE_VERSION = "v20.18.1"
NODE_URL = f"https://nodejs.org/dist/{NODE_VERSION}/node-{NODE_VERSION}-win-x64.zip"

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
            member = next(n for n in zf.namelist() if os.path.basename(n).lower() == target["name"].lower())
            with zf.open(member) as src, open(dest, "wb") as out:
                out.write(src.read())
    print(f"  wrote {dest} ({os.path.getsize(dest):,} bytes)")


def fetch_node() -> None:
    dest = os.path.join(BIN, "node.exe")
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print("  exists: node.exe")
        return
    print(f"  downloading node.exe <- {NODE_URL}")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "node.zip")
        urllib.request.urlretrieve(NODE_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            member = next(n for n in zf.namelist() if n.endswith("/node.exe"))
            with zf.open(member) as src, open(dest, "wb") as out:
                out.write(src.read())
    print(f"  wrote {dest} ({os.path.getsize(dest):,} bytes)")


def fetch_gltf_pipeline() -> None:
    """npm-install gltf-pipeline into bin/gltfpipe (build host needs npm; bundled offline thereafter)."""
    prefix = os.path.join(BIN, "gltfpipe")
    entry = os.path.join(prefix, "node_modules", "gltf-pipeline", "bin", "gltf-pipeline.js")
    if os.path.isfile(entry):
        print("  exists: gltf-pipeline")
        return
    os.makedirs(prefix, exist_ok=True)
    print("  npm install gltf-pipeline -> bin/gltfpipe")
    subprocess.run(
        f'npm install --prefix "{prefix}" gltf-pipeline --no-audit --no-fund',
        shell=True,
        check=True,
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    os.makedirs(BIN, exist_ok=True)
    for target in TARGETS:
        fetch(target)
    # Draco is the spec default (§1/§5.1), so its Node + gltf-pipeline toolchain is fetched by default.
    # `--no-draco` makes a minimal bundle (meshopt/quantize only, no KHR_draco_mesh_compression).
    if "--no-draco" not in argv:
        fetch_node()
        fetch_gltf_pipeline()
    print("binaries ready in bin/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
