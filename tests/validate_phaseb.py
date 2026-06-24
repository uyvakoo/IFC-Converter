"""
Assertion suite for the next-two-up-the-ladder cores: F6 batch + F7 licensing (headless).
    python tests/validate_phaseb.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import licensing
from core import batch
from core.errors import FatalError

FIXTURE = os.path.join(HERE, "fixtures", "fixture.ifc")
IFCCONVERT = os.path.join(ROOT, "bin", "IfcConvert.exe")
OUT = os.path.join(HERE, "_out_b")

_results = []


def check(name, cond, detail=""):
    _results.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


# ---- F6 batch -------------------------------------------------------------
def f6_batch():
    print("F6  batch orchestration")
    missing = os.path.join(OUT, "_nope.ifc")
    statuses = batch.run_batch(
        [FIXTURE, missing, FIXTURE],
        out_dir=OUT,
        groups=["Structural"],
        targets=("glb",),
        ifcconvert=IFCCONVERT,
    )
    states = [s.state for s in statuses]
    check("processes all 3 sequentially", len(statuses) == 3)
    check("good/bad/good -> Done,Error,Done", states == ["Done", "Error", "Done"], str(states))
    check("bad file isolated (has error msg)", statuses[1].error is not None)

    # cooperative cancel: allow file 0, cancel before file 1
    seen = {"n": 0}

    def cancel():
        seen["n"] += 1
        return seen["n"] > 1  # False for file 0, True from file 1 on

    statuses = batch.run_batch(
        [FIXTURE, FIXTURE, FIXTURE],
        out_dir=OUT,
        groups=["Structural"],
        targets=("glb",),
        ifcconvert=IFCCONVERT,
        cancel=cancel,
    )
    states = [s.state for s in statuses]
    check("cancel stops after first file", states == ["Done", "Cancelled", "Cancelled"], str(states))

    # fatal: missing binary aborts whole batch
    try:
        batch.run_batch(
            [FIXTURE], out_dir=OUT, groups=["Structural"], ifcconvert=os.path.join(ROOT, "bin", "NOPE.exe")
        )
        check("missing binary raises FatalError", False)
    except FatalError:
        check("missing binary raises FatalError", True)


# ---- F7 licensing ---------------------------------------------------------
def f7_licensing():
    print("F7  licensing (RSA + clock guard)")
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # 4096 in prod (D-note)
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    M = "MACHINE-A"
    future = (date.today() + timedelta(days=30)).isoformat()
    past = (date.today() - timedelta(days=1)).isoformat()

    good = licensing.sign_license(priv, M, future)
    check("valid license accepted", licensing.verify_license(good, pub_pem, current_machine=M).ok)
    check(
        "wrong machine rejected", not licensing.verify_license(good, pub_pem, current_machine="MACHINE-B").ok
    )

    expired = licensing.sign_license(priv, M, past)
    r = licensing.verify_license(expired, pub_pem, current_machine=M)
    check("expired rejected", (not r.ok) and "expired" in r.reason.lower(), r.reason)

    tampered = dict(good)
    tampered["expiry"] = (date.today() + timedelta(days=3650)).isoformat()
    check(
        "tampered payload rejected (sig mismatch)",
        not licensing.verify_license(tampered, pub_pem, current_machine=M).ok,
    )

    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = licensing.sign_license(other, M, future)
    check(
        "foreign-key signature rejected", not licensing.verify_license(forged, pub_pem, current_machine=M).ok
    )

    # clock guard
    now = datetime(2026, 6, 24, tzinfo=timezone.utc)
    store = licensing.InMemoryStore()
    check("first run ok + stamps", licensing.check_clock(store, now)[0])
    check("same/later time ok", licensing.check_clock(store, now + timedelta(days=1))[0])
    ok, reason = licensing.check_clock(store, now - timedelta(days=5))  # rolled back
    check("rolled-back clock locked", (not ok) and "tamper" in reason.lower(), reason)


def main():
    import shutil

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    f6_batch()
    f7_licensing()
    p, t = sum(_results), len(_results)
    print(f"\n==== {p}/{t} checks passed ====")
    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    main()
