#!/usr/bin/env python3
"""
Acceptance report (spec §8.4) — drives the **built bundle** through real conversions on Windows and
writes a Markdown test report with pass/fail + actual output sizes.

    python scripts/acceptance_report.py [path\\to\\IFC_Converter.exe] [out_dir]

Defaults: dist\\IFC_Converter\\IFC_Converter.exe, ./acceptance_out. This produces the automatable part
of the §8.4 artifact; the contractual clean-VM run + screenshots + human signature remain manual.
"""

from __future__ import annotations

import hashlib
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


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_selftest():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([EXE, "--selftest"], capture_output=True, text=True, env=env, timeout=120)
    out = (r.stdout or "") + (r.stderr or "")
    line = next((ln for ln in out.splitlines() if "selftest:" in ln), out.strip().splitlines()[-1:] or "")
    return r.returncode == 0, (line if isinstance(line, str) else "selftest output unavailable")


def main():
    os.makedirs(OUT, exist_ok=True)
    st_ok, st_line = run_selftest()
    exe_sha = sha256(EXE)
    gen = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
        f"- Generated: {gen}",
        f"- Host: {platform.platform()} / Python {platform.python_version()}",
        f"- Bundle under test: `{os.path.basename(EXE)}`",
        f"- Bundle SHA256: `{exe_sha}`",
        f"- Self-test: **{'PASS' if st_ok else 'FAIL'}** — `{st_line.strip()}`",
        f"- Conversions: **{passed}/{len(CASES)} cases passed**",
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
        "## §8.4 clean-VM acceptance checklist",
        "Run this report **on a fresh Windows 10/11 VM with no Python installed, offline**, then tick:",
        "",
        "- [ ] Copied `dist/IFC_Converter/` to the clean VM; `IFC_Converter.exe` launches (no Python).",
        "- [ ] `IFC_Converter.exe --selftest` prints `selftest: 9/9 OK` (technical result above).",
        "- [ ] License Activation window shows the machine hash; a signed license activates the app.",
        "- [ ] A real GUI conversion (GLB + STP) completes; the colored model opens in a glTF viewer.",
        "- [ ] Screenshots of the GUI + output captured and attached alongside this report.",
        "",
        "## Sign-off",
        "| Field | Value |",
        "|-------|-------|",
        "| Tester (name) | __________________________ |",
        "| Date | __________________________ |",
        "| Clean VM (OS / build) | __________________________ |",
        "| Python absent on VM? | ☐ confirmed |",
        "| Result | ☐ PASS  ☐ FAIL |",
        "| Signature | __________________________ |",
        "",
        f"_Auto-filled technical section generated {gen}; "
        "the checklist + sign-off are completed by hand on the clean VM (spec §8.4)._",
        "",
    ]
    report = os.path.join(OUT, "ACCEPTANCE-REPORT.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"selftest {'PASS' if st_ok else 'FAIL'}; {passed}/{len(CASES)} cases passed -> {report}")
    return 0 if (st_ok and passed == len(CASES)) else 1


if __name__ == "__main__":
    sys.exit(main())
