"""
Assertion suite for §9 error-handling scenarios (corrupt/missing input, disk-full, no-match).
Run from project root:  python tests/validate_errors.py
"""

from __future__ import annotations

import collections
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from core import batch, filtering, pipeline
from core.errors import FatalError, FileError

FIXTURE = os.path.join(HERE, "fixtures", "fixture.ifc")
IFCCONVERT = os.path.join(ROOT, "bin", "IfcConvert.exe")
OUT = os.path.join(HERE, "_out_err")

_results = []


def check(name, cond, detail=""):
    _results.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def _raises(fn, exc):
    try:
        fn()
    except exc as e:
        return str(e)
    except Exception as e:  # wrong type
        return f"!WRONG-TYPE:{type(e).__name__}:{e}"
    return "!NO-RAISE"


def scenario_1_bad_input():
    print("§9.1  scenario 1 — corrupt / missing / invalid input")
    msg = _raises(lambda: pipeline.process("does_not_exist.ifc", OUT, filtering.ALL_GROUPS), FileError)
    check("missing file -> FileError", msg.startswith("File not found"), msg)

    fd, garbage = tempfile.mkstemp(suffix=".ifc")
    os.write(fd, b"this is not an IFC file at all\n" * 5)
    os.close(fd)
    msg = _raises(lambda: pipeline.process(garbage, OUT, filtering.ALL_GROUPS), FileError)
    os.remove(garbage)
    check("corrupt file -> clear FileError (not a raw crash)", "Cannot read IFC" in msg, msg)


def scenario_5_no_match():
    print("§9    scenario 5 — selection/crop matches nothing")
    far = [1.0e7, 1.0e7 + 1, 1.0e7, 1.0e7 + 1, 1.0e7, 1.0e7 + 1]
    msg = _raises(
        lambda: pipeline.process(FIXTURE, OUT, filtering.ALL_GROUPS, xyz=far, ifcconvert=IFCCONVERT),
        FileError,
    )
    check("empty crop -> FileError 'nothing to export'", "nothing to export" in msg, msg)
    glb = os.path.join(OUT, "fixture.glb")
    check("no empty GLB written when nothing matched", not os.path.exists(glb))


def scenario_3_disk_full():
    print("§9.3  scenario 3 — disk full")
    du = collections.namedtuple("du", "total used free")
    orig = pipeline.shutil.disk_usage
    pipeline.shutil.disk_usage = lambda _p: du(100, 100, 0)  # zero free
    try:
        msg = _raises(
            lambda: pipeline.process(FIXTURE, OUT, filtering.ALL_GROUPS, ifcconvert=IFCCONVERT),
            FatalError,
        )
    finally:
        pipeline.shutil.disk_usage = orig
    check("no free space -> FatalError (aborts run)", "disk space" in msg.lower(), msg)


def batch_isolation():
    print("§9.1  batch isolation — bad file errors, queue continues")
    fd, garbage = tempfile.mkstemp(suffix=".ifc")
    os.write(fd, b"garbage\n")
    os.close(fd)
    st = batch.run_batch(
        [garbage, FIXTURE],
        out_dir=OUT,
        groups=filtering.ALL_GROUPS,
        targets=("glb",),
        ifcconvert=IFCCONVERT,
    )
    os.remove(garbage)
    check(
        "bad file -> Error, good file -> Done",
        [s.state for s in st] == ["Error", "Done"],
        str([s.state for s in st]),
    )
    check("bad file carries a clear message", "Cannot read IFC" in (st[0].error or ""), st[0].error)
    rp = os.path.join(OUT, "conversion_report.txt")
    text = open(rp).read() if os.path.exists(rp) else ""
    check("report logs both an Error row and a Done row", "status=Error" in text and "status=Done" in text)


def batch_fatal_aborts():
    print("§9.3  disk-full FatalError aborts the batch")
    du = collections.namedtuple("du", "total used free")
    orig = pipeline.shutil.disk_usage
    pipeline.shutil.disk_usage = lambda _p: du(100, 100, 0)
    try:
        msg = _raises(
            lambda: batch.run_batch(
                [FIXTURE], out_dir=OUT, groups=filtering.ALL_GROUPS, ifcconvert=IFCCONVERT
            ),
            FatalError,
        )
    finally:
        pipeline.shutil.disk_usage = orig
    check("run_batch re-raises FatalError (whole-run abort)", "disk space" in msg.lower(), msg)


def cli_exit_codes():
    print("§9 cli.main exit codes (in-process: 1 per-file error, 0 success)")
    import cli

    far = "10000000,10000001,10000000,10000001,10000000,10000001"
    with tempfile.TemporaryDirectory() as tmp:
        garbage = os.path.join(tmp, "g.ifc")
        with open(garbage, "w") as f:
            f.write("this is not an IFC file\n")
        missing = os.path.join(tmp, "no_such.ifc")

        def m(args):
            return cli.main([*args, "--ifcconvert", IFCCONVERT])

        check("corrupt -> exit 1", m([garbage, "--out", os.path.join(tmp, "a"), "--glb"]) == 1)
        check("missing -> exit 1", m([missing, "--out", os.path.join(tmp, "b"), "--glb"]) == 1)
        check(
            "no-match crop -> exit 1",
            m([FIXTURE, "--out", os.path.join(tmp, "c"), "--xyz", far, "--glb"]) == 1,
        )
        check(
            "all-good -> exit 0",
            m([FIXTURE, "--out", os.path.join(tmp, "d"), "--classes", "Structural,MEP", "--glb"]) == 0,
        )
        check(
            "batch [bad, good] -> exit 1 (queue continues)",
            m([garbage, FIXTURE, "--out", os.path.join(tmp, "e"), "--classes", "Structural,MEP", "--glb"])
            == 1,
        )


def main():
    import shutil

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    scenario_1_bad_input()
    scenario_5_no_match()
    scenario_3_disk_full()
    batch_isolation()
    batch_fatal_aborts()
    cli_exit_codes()
    p, t = sum(_results), len(_results)
    print(f"\n==== {p}/{t} checks passed ====")
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
