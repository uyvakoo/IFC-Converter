#!/usr/bin/env python3
"""
Validate real Draco compression through the BUILT bundle (--cli --compress-mode draco).

Asserts the bundle's gltf-pipeline backend produces a GLB that declares KHR_draco_mesh_compression
and keeps its materials. Skips cleanly if the bundle was built without --with-draco (no node.exe).

    python scripts/draco_check.py [path\\to\\IFC_Converter.exe]
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import tempfile

import _qa_license  # sibling helper: signs a machine-locked --license for the hardened --cli gate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures")
EXE = os.path.abspath(
    sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "IFC_Converter", "IFC_Converter.exe")
)


def _glb_json(path):
    data = open(path, "rb").read()
    if data[:4] != b"glTF":
        return None
    clen = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20 : 20 + clen])


def main():
    if not os.path.isfile(EXE):
        print(f"bundle not found: {EXE}")
        return 2
    bundled_node = os.path.join(os.path.dirname(EXE), "_internal", "bin", "node.exe")
    if not os.path.isfile(bundled_node):
        print("SKIP: bundle has no node.exe (build with fetch_binaries.py --with-draco)")
        return 0
    with tempfile.TemporaryDirectory() as out:
        # The frozen `--cli` requires a valid machine-locked key (PR #14); sign one for this run.
        license_path = _qa_license.mint()
        cmd = [
            EXE, "--cli", os.path.join(FIX, "real_building.ifc"), "--out", out,
            "--classes", "Structural,MEP,Architectural", "--glb", "--compress", "--compress-mode", "draco",
            "--license", license_path,
        ]  # fmt: skip
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        glb = os.path.join(out, "real_building.glb")
        print((r.stdout or "").strip() or (r.stderr or "").strip())
        if r.returncode != 0 or not os.path.isfile(glb):
            print(f"FAIL: exit {r.returncode}, no GLB")
            return 1
        j = _glb_json(glb)
        exts = (j or {}).get("extensionsRequired", [])
        mats = [m.get("name") for m in (j or {}).get("materials", [])]
        ok = "KHR_draco_mesh_compression" in exts and any(mats)
        print(f"extensionsRequired={exts}  materials={mats}  size={os.path.getsize(glb)}")
        print("==== DRACO PASS (frozen bundle) ====" if ok else "==== DRACO FAIL ====")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
