"""
F5 (AR optimization) — GLB post-compression, pluggable backend.

IfcConvert has no --draco/--optimize (D1), so this module reproduces the spec's mandated
`--draco --optimize` (§1, §5.1: "highly compressed, low-poly" AR GLB) as a post-step on the plain GLB:

  mode="draco"   (default, spec) — gltfpack -si (low-poly) + gltf-pipeline -d  -> KHR_draco_mesh_compression
  mode="meshopt"                 — gltfpack -si -cc  -> EXT_meshopt_compression (~3x smaller)
  mode="quantize"                — gltfpack -si      -> KHR_mesh_quantization only (broadest loader compat)

The `-optimize`/low-poly step (gltfpack -si triangle decimation) applies to ALL modes, so draco is now
both decimated AND Draco-compressed. `-kn`/`-km` keep node + material names so the assigned colours and
per-element traceability survive every stage.
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


def compress_glb(
    gltfpack: str,
    glb_path: str,
    *,
    mode: str = "meshopt",
    simplify: float = 0.5,
    node: str | None = None,
    gltf_pipeline: str | None = None,
) -> dict:
    """Optimize `glb_path` in place. Returns {mode, bytes_before, bytes_after, ratio}.

    meshopt/quantize use gltfpack; draco decimates with gltfpack then Draco-encodes via
    `node gltf-pipeline.js -d` (KHR_draco_mesh_compression). `simplify` (low-poly) applies to all modes.
    """
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
            if not node or not os.path.isfile(node):
                raise RuntimeError(f"draco mode requires the bundled Node runtime (node={node!r})")
            if not gltf_pipeline or not os.path.isfile(gltf_pipeline):
                raise RuntimeError(
                    f"draco mode requires the bundled gltf-pipeline (gltf_pipeline={gltf_pipeline!r})"
                )
            # Stage 1 (the spec's --optimize / low-poly): gltfpack -si decimates. -noq keeps geometry
            # un-quantized so Draco is the sole mesh compression (no KHR_mesh_quantization clash);
            # -kn/-km preserve the assigned colours. Skipped when simplify disables decimation.
            if simplify and simplify < 1.0:
                _run(
                    [gltfpack, "-i", glb_path, "-o", tmp, "-si", str(simplify), "-noq", "-kn", "-km"],
                    glb_path,
                    tmp,
                )
                fd2, tmp = tempfile.mkstemp(suffix=".glb")  # fresh scratch for stage 2
                os.close(fd2)
            # Stage 2 (the spec's --draco): KHR_draco_mesh_compression via gltf-pipeline.
            _run([node, gltf_pipeline, "-i", glb_path, "-o", tmp, "-d"], glb_path, tmp)
        else:
            raise ValueError(f"unknown compress mode: {mode!r}")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    after = os.path.getsize(glb_path)
    return {
        "mode": mode,
        "bytes_before": before,
        "bytes_after": after,
        "ratio": round(after / before, 3) if before else None,
    }
