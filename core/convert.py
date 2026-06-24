"""
F4/F5 (core) — IfcConvert subprocess wrapper.

Runs the official IfcConvert CLI on an already-written IFC. GLB keeps the colors via
`--use-material-names`; STP is plain geometry. No `--draco/--optimize` (don't exist, D1) — Draco is a
separate gltfpack post-step (F5, to be added). IfcConvert prints UTF-16 on Windows, so output is
decoded accordingly for logging.
"""
from __future__ import annotations

import os
import subprocess

from .errors import FatalError


def ensure_available(*tool_paths: str) -> None:
    """Fail fast (FatalError, §9.3) if any bundled binary is missing/non-executable."""
    for p in tool_paths:
        if not p or not os.path.isfile(p):
            raise FatalError(f"required bundled binary not found: {p}")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True)
    # IfcConvert emits UTF-16LE on Windows; decode leniently for logs.
    r_stdout = (r.stdout or b"").decode("utf-16-le", "ignore")
    r_stderr = (r.stderr or b"").decode("utf-16-le", "ignore")
    return subprocess.CompletedProcess(cmd, r.returncode, r_stdout, r_stderr)


def to_glb(ifcconvert: str, ifc_path: str, out_glb: str) -> str:
    """Convert to GLB (Y-up, colors preserved). Retries without --use-material-names if rejected."""
    base = [ifcconvert, "-y", "--y-up"]  # -y: auto-overwrite existing output
    r = _run(base + ["--use-material-names", ifc_path, out_glb])
    if r.returncode != 0 and "use-material-names" in (r.stdout + r.stderr):
        r = _run(base + [ifc_path, out_glb])
    if r.returncode != 0:
        raise RuntimeError(f"IfcConvert GLB failed (exit {r.returncode}): {r.stderr.strip()}")
    return out_glb


def to_stp(ifcconvert: str, ifc_path: str, out_stp: str) -> str:
    """Convert to STP/STEP (clean geometry, no colors)."""
    r = _run([ifcconvert, "-y", "--convert-back-units", ifc_path, out_stp])
    if r.returncode != 0:
        raise RuntimeError(f"IfcConvert STP failed (exit {r.returncode}): {r.stderr.strip()}")
    return out_stp
