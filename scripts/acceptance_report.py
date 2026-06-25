#!/usr/bin/env python3
"""
Acceptance report (spec §8.4) — drives the **built bundle** through real conversions on Windows and
writes a Markdown test report with pass/fail + actual output sizes.

    python scripts/acceptance_report.py [path\\to\\IFC_Converter.exe] [out_dir]

Defaults: dist\\IFC_Converter\\IFC_Converter.exe, ./acceptance_out. This produces the automatable part
of the §8.4 artifact; the contractual clean-VM run + screenshots + human signature remain manual.
"""

from __future__ import annotations

import json
import os
import platform
import struct
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures")

EXE = os.path.abspath(
    sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "IFC_Converter", "IFC_Converter.exe")
)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "acceptance_out")

CASES = [
    ("fixture: Structural+MEP -> GLB", "fixture.ifc", ["--classes", "Structural,MEP", "--glb"]),
    (
        "fixture: crop to Ground -> GLB+STP",
        "fixture.ifc",
        ["--classes", "Structural,MEP,Architectural,Cables", "--storey", "Ground", "--glb", "--stp"],
    ),
    ("real model: Structural -> GLB", "real_building.ifc", ["--classes", "Structural", "--glb"]),
    (
        "real model: Structural -> compressed GLB",
        "real_building.ifc",
        ["--classes", "Structural", "--glb", "--compress"],
    ),
    (
        "real model: all -> GLB+STP",
        "real_building.ifc",
        ["--classes", "Structural,MEP,Architectural,Cables", "--glb", "--stp"],
    ),
]


def glb_materials(path):
    data = open(path, "rb").read()
    if data[:4] != b"glTF":
        return None
    clen = struct.unpack_from("<I", data, 12)[0]
    return [m.get("name") for m in json.loads(data[20 : 20 + clen]).get("materials", [])]


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, passed = [], 0
    for name, fixture, args in CASES:
        ifc = os.path.join(FIX, fixture)
        cmd = [EXE, "--cli", ifc, "--out", OUT] + args
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = -1  # treated as failure below
        stem = os.path.splitext(fixture)[0]
        glb = os.path.join(OUT, stem + ".glb")
        stp = os.path.join(OUT, stem + ".stp")
        glb_sz = os.path.getsize(glb) if os.path.exists(glb) else 0
        stp_sz = os.path.getsize(stp) if os.path.exists(stp) else 0
        mats = glb_materials(glb) if glb_sz else None
        ok = rc == 0 and ("--glb" not in args or (glb_sz > 0 and mats))
        ok = ok and ("--stp" not in args or stp_sz > 0)
        passed += ok
        rows.append((name, "PASS" if ok else "FAIL", glb_sz, stp_sz, ",".join(m for m in (mats or []) if m)))

    lines = [
        "# IFC Converter — Acceptance Report (§8.4)",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Host: {platform.platform()} / Python {platform.python_version()}",
        f"- Bundle under test: `{os.path.basename(EXE)}`",
        f"- Result: **{passed}/{len(CASES)} cases passed**",
        "",
        "All conversions below were executed by the **built bundle** (`--cli`), not the dev tree.",
        "",
        "| Case | Result | GLB bytes | STP bytes | GLB materials |",
        "|------|--------|-----------|-----------|----------------|",
    ]
    for name, res, g, s, m in rows:
        lines.append(f"| {name} | {res} | {g or '-'} | {s or '-'} | {m or '-'} |")
    lines += [
        "",
        "## Manual residual (owner)",
        "- Run this bundle on a **clean Windows VM with no Python, offline**, plus a GUI conversion.",
        "- Capture **screenshots** and **sign** this report. See `BUILD.md` §9.",
        "",
    ]
    report = os.path.join(OUT, "ACCEPTANCE-REPORT.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{passed}/{len(CASES)} cases passed -> {report}")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
