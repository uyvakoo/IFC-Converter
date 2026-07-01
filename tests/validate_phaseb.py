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
    check(
        "expired rejected (exact spec message)",
        (not r.ok) and r.reason == "Invalid license - contact vendor",
        r.reason,
    )

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

    # verify_file (on-disk key path)
    import json as _json
    import tempfile as _tmp

    check("verify_file: no path rejected", not licensing.verify_file(None).ok)
    with _tmp.TemporaryDirectory() as _td:
        check("verify_file: missing file rejected", not licensing.verify_file(os.path.join(_td, "x.key")).ok)
        import licensing.core as _lc

        _op, _om = _lc.load_public_key_pem, _lc.machine_hash
        _lc.load_public_key_pem, _lc.machine_hash = (lambda: pub_pem), (lambda: M)
        try:
            gp = os.path.join(_td, "good.key")
            open(gp, "w", encoding="utf-8").write(_json.dumps(good))
            check("verify_file: valid key file for this machine accepted", licensing.verify_file(gp).ok)
            fp = os.path.join(_td, "forged.key")
            open(fp, "w", encoding="utf-8").write(_json.dumps(forged))
            check("verify_file: foreign key file rejected", not licensing.verify_file(fp).ok)
        finally:
            _lc.load_public_key_pem, _lc.machine_hash = _op, _om

    # clock guard
    now = datetime(2026, 6, 24, tzinfo=timezone.utc)
    store = licensing.InMemoryStore()
    check("first run ok + stamps", licensing.check_clock(store, now)[0])
    check("same/later time ok", licensing.check_clock(store, now + timedelta(days=1))[0])
    ok, reason = licensing.check_clock(store, now - timedelta(days=5))  # rolled back
    check("rolled-back clock locked", (not ok) and "tamper" in reason.lower(), reason)

    # clock guard via the REAL HKCU registry store (the production path)
    if sys.platform == "win32":
        import winreg

        subkey = r"Software\IFCConverter_test"
        reg = licensing.RegistryStore(subkey=subkey)
        try:
            ok1, _ = licensing.check_clock(reg, now)
            ok2, _ = licensing.check_clock(reg, now + timedelta(days=1))
            persisted = reg.get()
            ok3, rreason = licensing.check_clock(reg, now - timedelta(days=5))
            check("registry: first-run + later ok", ok1 and ok2)
            check(
                "registry: value persisted to HKCU",
                persisted == (now + timedelta(days=1)).isoformat(),
                str(persisted),
            )
            check("registry: rollback locked", (not ok3) and "tamper" in rreason.lower(), rreason)
        finally:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
            except OSError:
                pass
    else:
        check("registry store (skipped: not Windows)", True)

    # NTP cross-check (§6.2): system clock far behind true time -> tampered.
    real = now + timedelta(days=30)
    check(
        "NTP: clock far behind real time locks",
        not licensing.check_clock(licensing.InMemoryStore(), now - timedelta(days=2), ntp=real)[0],
    )
    check(
        "NTP: clock within tolerance ok",
        licensing.check_clock(licensing.InMemoryStore(), now, ntp=now + timedelta(hours=1))[0],
    )
    live = licensing.ntp_utc(timeout=3)
    if live is not None:
        skew = abs((live - datetime.now(timezone.utc)).total_seconds())
        check(
            "live NTP returns UTC near system time", live.tzinfo is not None and skew < 86400, f"{skew:.0f}s"
        )
    else:
        check("live NTP unreachable -> graceful None (air-gapped path)", True)

    # bundled PRODUCTION public key must be 4096-bit (§6.2)
    bundled = serialization.load_pem_public_key(licensing.load_public_key_pem())
    check("bundled production key is 4096-bit", bundled.key_size == 4096, str(bundled.key_size))


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
