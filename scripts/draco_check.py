#!/usr/bin/env python3
"""
Validate real Draco compression through the BUILT bundle (--cli --compress-mode draco).

Asserts the bundle's gltf-pipeline backend produces a GLB that declares KHR_draco_mesh_compression
and keeps its materials. Skips cleanly if the bundle was built with --no-draco (no node.exe).

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


def _triangles(j):
    """Sum triangles from index-accessor counts (present in JSON even after Draco encoding)."""
    n = 0
    for mesh in (j or {}).get("meshes", []):
        for prim in mesh.get("primitives", []):
            idx = prim.get("indices")
            if idx is not None:
                n += j["accessors"][idx]["count"] // 3
    return n


def main():
    if not os.path.isfile(EXE):
        print(f"bundle not found: {EXE}")
        return 2
    bundled_node = os.path.join(os.path.dirname(EXE), "_internal", "bin", "node.exe")
    if not os.path.isfile(bundled_node):
        print("SKIP: bundle has no node.exe (built with fetch_binaries.py --no-draco)")
        return 0
    with tempfile.TemporaryDirectory() as out:
        # The frozen `--cli` requires a valid machine-locked key (PR #14); sign one for this run.
        license_path = _qa_license.mint()
        base = [
            EXE, "--cli", os.path.join(FIX, "real_building.ifc"),
            "--classes", "Structural,MEP,Architectural", "--glb", "--license", license_path,
        ]  # fmt: skip
        # Plain baseline (no --compress) for the size + triangle comparison.
        pout = os.path.join(out, "plain")
        subprocess.run(base + ["--out", pout], capture_output=True, text=True, timeout=300)
        plain_glb = os.path.join(pout, "real_building.glb")
        plain_tris = _triangles(_glb_json(plain_glb)) if os.path.isfile(plain_glb) else 0
        plain_size = os.path.getsize(plain_glb) if os.path.isfile(plain_glb) else 0
        # Draco run (spec default): KHR_draco_mesh_compression + colours preserved + smaller.
        dout = os.path.join(out, "draco")
        r = subprocess.run(
            base + ["--out", dout, "--compress", "--compress-mode", "draco"],
            capture_output=True, text=True, timeout=300,
        )  # fmt: skip
        glb = os.path.join(dout, "real_building.glb")
        print((r.stdout or "").strip() or (r.stderr or "").strip())
        if r.returncode != 0 or not os.path.isfile(glb):
            print(f"FAIL: exit {r.returncode}, no GLB")
            return 1
        j = _glb_json(glb)
        exts = (j or {}).get("extensionsRequired", [])
        mats = [m.get("name") for m in (j or {}).get("materials", [])]
        draco_tris = _triangles(j)
        draco_size = os.path.getsize(glb)
        has_draco = "KHR_draco_mesh_compression" in exts
        has_mats = any(mats)
        # real_building is box geometry (no decimation); Draco still shrinks it. The -si low-poly stage
        # is proven on a decimatable mesh by validate_core.m5_lowpoly().
        smaller = 0 < draco_size < plain_size
        ok = has_draco and has_mats and smaller
        print(
            f"extensionsRequired={exts}  materials={mats}  "
            f"triangles={plain_tris}->{draco_tris}  size={plain_size}->{draco_size}"
        )
        print("==== DRACO PASS (frozen bundle) ====" if ok else "==== DRACO FAIL ====")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
