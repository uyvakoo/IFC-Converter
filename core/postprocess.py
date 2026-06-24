"""
F5 (AR optimization) — GLB post-compression, pluggable backend.

IfcConvert can't compress (no --draco/--optimize, D1). This module decimates + compresses the plain
GLB in place. Two modes so the client's ARKit decoder decision (open D1 sub-item) is a config switch,
not a rewrite:

  mode="meshopt"  (default) — gltfpack -si -cc  -> EXT_meshopt_compression (validated, ~3x smaller)
  mode="quantize"           — gltfpack -si      -> KHR_mesh_quantization only (broadest loader compat)
  mode="draco"              — gltf-pipeline -d  -> KHR_draco_mesh_compression (needs bundled Node tool)

`-kn`/`-km` keep node + material names so colored materials and per-element traceability survive.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile


def _run(cmd, glb_path, tmp):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(tmp) or not os.path.getsize(tmp):
        raise RuntimeError(f"{os.path.basename(cmd[0])} failed (exit {r.returncode}): {r.stderr.strip()}")
    shutil.move(tmp, glb_path)


def compress_glb(gltfpack: str, glb_path: str, *, mode: str = "meshopt", simplify: float = 0.5,
                 gltf_pipeline: str | None = None) -> dict:
    """Optimize `glb_path` in place. Returns {mode, bytes_before, bytes_after, ratio}."""
    before = os.path.getsize(glb_path)
    fd, tmp = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        if mode in ("meshopt", "quantize"):
            cmd = [gltfpack, "-i", glb_path, "-o", tmp, "-kn", "-km"]
            if simplify and simplify < 1.0:
                cmd += ["-si", str(simplify)]
            if mode == "meshopt":
                cmd += ["-cc"]
            _run(cmd, glb_path, tmp)
        elif mode == "draco":
            if not gltf_pipeline or not os.path.isfile(gltf_pipeline):
                raise RuntimeError("draco mode requires a bundled gltf-pipeline binary "
                                   "(set gltf_pipeline=...); see D1 open sub-item")
            _run([gltf_pipeline, "-i", glb_path, "-o", tmp, "-d"], glb_path, tmp)
        else:
            raise ValueError(f"unknown compress mode: {mode!r}")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    after = os.path.getsize(glb_path)
    return {"mode": mode, "bytes_before": before, "bytes_after": after,
            "ratio": round(after / before, 3) if before else None}
