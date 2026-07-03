#!/usr/bin/env python3
"""
Exit-code acceptance for the §9 error scenarios, driven through the **built bundle** (`--cli`).

Asserts the *real* process exit code via subprocess.run(...).returncode — no shell pipes (an earlier
manual check piped through `tail` and read tail's exit, not the exe's). Per-file errors must exit 1,
fatal errors exit 2, a clean run exits 0; side effects (no empty GLB, queue keeps going, report rows)
are checked too.

    python scripts/cli_exit_codes.py [path\\to\\IFC_Converter.exe]

Exits non-zero if any case mismatches. Fast enough to run in CI right after --selftest.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import _qa_license  # sibling helper: signs a machine-locked --license for the hardened --cli gate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures")
FIXTURE = os.path.join(FIX, "fixture.ifc")

EXE = os.path.abspath(
    sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "IFC_Converter", "IFC_Converter.exe")
)

# The frozen `--cli` now requires a valid machine-locked key (PR #14); mint one for these runs.
LICENSE = _qa_license.mint()

_results = []


def check(name, cond, detail=""):
    _results.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def run(exe_args, out, license_path=LICENSE):
    os.makedirs(out, exist_ok=True)
    cmd = [EXE, "--cli", *exe_args, "--out", out]
    if license_path is not None:
        cmd += ["--license", license_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    if not os.path.isfile(EXE):
        print(f"bundle not found: {EXE}")
        return 2
    far = "10000000,10000001,10000000,10000001,10000000,10000001"
    with tempfile.TemporaryDirectory() as tmp:
        garbage = os.path.join(tmp, "garbage.ifc")
        with open(garbage, "w") as f:
            f.write("this is not an IFC file\n")
        missing = os.path.join(tmp, "does_not_exist.ifc")

        print("§9 exit codes via the frozen exe")

        # PR #14 gate: --cli without a valid license must refuse (exit 2) before any conversion.
        o0 = os.path.join(tmp, "o0")
        rc, _ = run([FIXTURE, "--classes", "Structural,MEP", "--glb"], o0, license_path=None)
        check("no license -> exit 2 (gate)", rc == 2, f"exit {rc}")
        check("no license -> no GLB written", not os.path.exists(os.path.join(tmp, "o0", "fixture.glb")))

        rc, _ = run([garbage, "--glb"], os.path.join(tmp, "o1"))
        check("corrupt input -> exit 1", rc == 1, f"exit {rc}")
        check("corrupt input -> no GLB", not os.path.exists(os.path.join(tmp, "o1", "garbage.glb")))

        rc, _ = run([missing, "--glb"], os.path.join(tmp, "o2"))
        check("missing input -> exit 1", rc == 1, f"exit {rc}")

        rc, _ = run([FIXTURE, "--xyz", far, "--glb"], os.path.join(tmp, "o3"))
        check("no-match crop -> exit 1", rc == 1, f"exit {rc}")
        check("no-match crop -> no empty GLB", not os.path.exists(os.path.join(tmp, "o3", "fixture.glb")))

        ob = os.path.join(tmp, "o4")
        rc, _ = run([garbage, FIXTURE, "--classes", "Structural,MEP", "--glb"], ob)
        check("batch [bad, good] -> exit 1", rc == 1, f"exit {rc}")
        check("batch: good file still produced its GLB", os.path.exists(os.path.join(ob, "fixture.glb")))
        rpt = (
            open(os.path.join(ob, "conversion_report.txt")).read()
            if os.path.exists(os.path.join(ob, "conversion_report.txt"))
            else ""
        )
        check(
            "batch: report logs an Error row AND a Done row", "status=Error" in rpt and "status=Done" in rpt
        )

        og = os.path.join(tmp, "o5")
        rc, _ = run([FIXTURE, "--classes", "Structural,MEP", "--glb"], og)
        check("all-good run -> exit 0", rc == 0, f"exit {rc}")
        check("all-good run -> GLB produced", os.path.exists(os.path.join(og, "fixture.glb")))

    p, t = sum(_results), len(_results)
    print(f"\n==== {p}/{t} checks passed ====")
    return 0 if p == t else 1


if __name__ == "__main__":
    sys.exit(main())
